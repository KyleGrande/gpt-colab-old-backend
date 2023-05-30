import os
import re
import sys
from io import StringIO
import shutil
import openai
import multiprocessing
import json
import base64
import tempfile
# KYLE : : :  : pip install nbformat nbclient, used for executing code in the notebook
import nbformat
from nbclient import NotebookClient
from nbconvert.preprocessors import ExecutePreprocessor
from nbformat.v4 import new_notebook, new_code_cell, new_markdown_cell
from io import BytesIO
from PIL import Image
import requests
# # KYLE : : :  : pip install tiktoken #Not implemented yet
# import tiktoken #OpenAI package: Used for checking number of tokens in a string, 
# # KYLE : : :  : pip install docker #Not implemented yet
# import docker
# import tarfile
# import io


class ChatAssistant:
    '''
    Chat Assistant class
    
    This class is used to create a chat assistant that can be used to interact with GPT-4
    
    Attributes:
        openai_api_key (str): The OpenAI API key to use
        messages (list): A list of messages that have been sent to the chat assistant
        previous_model (str): The model that was used to generate the previous message
        
    Methods:
        contextClassifier(self, most_recent_message: str, retries: int = 0):
        Selects the best prompt for the model to use based on the most recent message
    '''
    def __init__(self, openai_api_key: str, uuid: str = ""):
        '''
        Constructor for the ChatAssistant class
        '''
        
        openai.api_key = openai_api_key
        self.api_key = openai_api_key # The OpenAI API key to use

        self.messages = [
            {"role": "system", "content": "You are Babbage, an experimental AI system with the added capability of a built in python code compiler, access to local files uploaded to you, internet access, the ability to create images through dall-e, and recursive problem solving (by using your ability to send multiple responses, before presenting the final answer to a user). Answer as concisely as possible. To execute code, simply write your python program within code snippets. The interpreter will then send a message to you with the output of your program. You should explain the output and/or finish your problem solving using it in the next message. You have access to your local file system, but you must use code to view and interact with it. You have to ability to solve problems recursively. Use python programs for any problem if they are applicable, such as searching the web with googlesearch. You must use print statements to see the output. When given a file, write a python script to attempt to interpret it. You can open any type of file as long as you use the appropriate library. If the user asks you to use OCR to identify an image, use pytesseract and set the tesseract path to C:\Program Files\Tesseract-OCR\tesseract.exe"},
        ]

        self.previous_model = "standard"

        self.uuid = uuid

        #Create a notebook for the chat assistant to use, with the given UUID
        self.notebook = self.create_notebook(uuid)

        #List of files that have been uploaded to the chat assistant
        self.file_list = []

        #used for keeping track of the number of times the problem has been run recursively
        self.recursionAttempts = 0
        


    def create_notebook(self, uuid: str):
        '''
        Creates an IPython notebook with the given UUID.
        '''
        notebook = new_notebook()
        notebook.cells.append(new_markdown_cell(f"# Notebook for ChatAssistant {uuid}"))

        file_path = f"notebook_{uuid}.ipynb"
        with open(file_path, 'w', encoding='utf-8') as f:
            nbformat.write(notebook, f)

        return file_path
    
    def send_code_to_interpreter(self, code: str, timeout: int = 60):
        """
        Executes the code in the IPython notebook.
        Temporarily copies the notebook to a sandboxed directory to prevent the code from accessing other files.
        Temporarily copies all "files" from the notebook to the sandboxed directory to prevent the code from accessing the user's files.
        Limits the execution time of the code to prevent it from running indefinitely.
        Limits the amount of text that the code can pass to the model to prevent it from running out of tokens.
        """

        # Store the original working directory
        original_working_directory = os.getcwd()

        # Create a safe and isolated working directory
        safe_working_directory = tempfile.mkdtemp()

        #if code contains os.chdir, return error. This is to prevent the user from changing the directory of the interpreter
        if "os.chdir" in code:
            response = {
                        "result": "You are not allowed to change the directory of the interpreter."
                    }
            return response
        if "os.pardir" in code:
            response = {
                        "result": "You are not allowed to change the directory of the interpreter."
                    }
            return response
        #This is still a major security risk, as the user can still change the directory of the interpreter by encoding it in base64 and then decoding it in the interpreter

        try:
            # Copy the IPython notebook file to the safe directory
            notebook_filename = os.path.basename(self.notebook)
            notebook_temp_path = os.path.join(safe_working_directory, notebook_filename)
            shutil.copy(self.notebook, notebook_temp_path)

            # Read the notebook
            with open(notebook_temp_path, 'r', encoding='utf-8') as f:
                notebook = nbformat.read(f, nbformat.NO_CONVERT)

            #move files in file_list to safe_working_directory
            for file in self.file_list:
                shutil.copy(file, safe_working_directory)

            # Add the code to the notebook
            notebook.cells.append(new_code_cell(code))

            # Change the working directory to the safe_working_directory
            os.chdir(safe_working_directory)

            # Execute the code
            try:
                client = NotebookClient(notebook, timeout=timeout)
                client.execute()

                cell_output = client.nb.cells[-1]['outputs']
                if cell_output:
                    output = cell_output[0]['text'].strip()

                    print(f"Code output: {output}")
                else:
                    output = "Code executed successfully, but no output was detected. Please wait for the next user message before reattempting to write the code."

            except Exception as error:
                output = f"Failed to execute the code. Error: {str(error)}"

            with open(notebook_temp_path, 'w', encoding='utf-8') as f:
                nbformat.write(notebook, f)

                response = {
                    "result": output
                }

                # Truncate the result if it's too long
                if len(response['result']) > 1000:
                    response['result'] = response['result'][:1000] + "..."

        finally:
            # Restore the original working directory
            os.chdir(original_working_directory)

            # Clean up the temporary directory
            shutil.rmtree(safe_working_directory)

        return response
        
    def add_file_to_list(self, file_path: str):
        """
        Adds a file to the list of files that the interpreter can access.
        This allows the interpreter to access the file, once it is moved to the sandboxed environment.
        """
        #add file path to file list
        self.file_list.append(file_path)


    def contextClassifier(self, most_recent_message: str, retries: int = 0):
        '''
        Runs a classifier model with Davinci Instruct
        Selects the best prompt for the model to use based on the most recent message
        '''
        try:
            response = openai.Completion.create(
                model="text-davinci-003",
                prompt ="Decide what AI model to pass the message to. If the message has to do with math select \"math\", if the message has to do with \"code\" select \"code\", if the message has to do with internet access select \"internet\", if the model receives a message from the interpreter select \"file\", if the message has to do with downloading any kind of file select \"download\",If the message has to do with creating something other than code select \"creative\", if the message has to do with anything else select \"standard\"\n\nMessage: Search up \"ThePirateBay.com\" on google\nModel: Internet\nMessage: Solve for x in the equation 2x + 3 = 7\nModel: Math\nMessage: Write a program to print \"Hello World\"\nModel: Code\nMessage: What is the capital of France?\nModel: Standard\nMessage: Use the internet to find the capital of france\nModel: Internet\nMessage: File hello.png saved to disk successfully!\"\nModel: File\nMessage: make a download link for the file\nModel: Download\nMessage: create an imaage/picture of an astronaut\nModel: Creative\nMessage:"  + most_recent_message + "\nModel:",
                temperature=0,
                max_tokens=60,
                top_p=1,
                frequency_penalty=0.5,
                presence_penalty=0
            )

            print("Model Selected:", response.choices[0].text)
            self.previous_model = response.choices[0].text
            return response.choices[0].text
        
        # Handle rate limit errors
        except openai.error.RateLimitError as error:
            print(f"RateLimitError occurred: {error}")
            if retries < 2:
                # Try again, incrementing the retries count
                return self.contextClassifier(most_recent_message, retries=retries + 1)
            else:
                # If retries exceeded, return "standard"
                return "standard"
        except openai.error.APIError as error:
            print(f"APIError occurred: {error}")
            # Default to standard model
            return "standard"
        except Exception as error:
            print(f"An unexpected error occurred: {error}")
            # Default to standard model
            return "standard"

    def generate_gpt_response(self, messages: list,interpreterOutput: bool = False):
        '''
        Generates a response from GPT-4 based on the messages list
        '''
        #if the openai api key is not set, return an error message
        if self.api_key == "":
            return "Error: OpenAI API Key not set"
        

        #select the most recent message
        most_recent_message = messages[-1]['content']

        #delete the last message in the messages list
        del messages[-1]

        #call prompt selector if interpreterOutput is false
        if interpreterOutput == False:
            model = self.contextClassifier(most_recent_message)
        #Do not use a prompt selector if GPT is being fed the output of the interpreter
        elif interpreterOutput == True:
            # model = self.previous_model #use the same model as the previous message
            #CONSIDERATION: FOLLOW UP MODEL. May add this later
            # model = "followup" #use the folowup model
            model = "standard" #use the standard model
        else:
            model = "standard"

        #Format the model string
        #convert model to string
        model = str(model)
        #convert model to lowercase
        model = model.lower()
        #remove whitespace
        model = model.strip()

        # print(model)

        # Approach 2 Model Selection/Prompt Injection
        if model == "standard":
            #add the most recent message back to the messages list
            messages.append({"role": "user", "content": most_recent_message})
        # elif model == "code":
        #     #append the most recent message in the messages, with "hello" at the beginning
        #     messages.append({"role": "user", "content": "write a python snippet to solve the following issue or if there are none give an explanation of the code:::" + most_recent_message})
        elif model == "math":
            #append the most recent message in the messages, with "solve" at the beginning
            # messages.append({"role": "user", "content": "write a python snippet to solve the following math problem, be sure to use print statements so that you can view the results:::" + most_recent_message})
            messages.append({"role": "user", "content": "use python to solve the following problem:::" + most_recent_message})
        elif model == "internet":
            #append the most recent message in the messages, with "search" at the beginning
            messages.append({"role": "user", "content": "write a python snippet that uses google search (if using googlesearch use the param search() (and do not write num_results, write num instead) with only the query, no other params for links) or another web scraping package to obtain the web result, be sure to use print statements so that you can read it. If the user requests a specific web page then please try to get information from that specific page. Once the interpreter returns the results, Don't spam links in your response. Instead concisely answer the user's request and include only relevent links (and only if you think it is relevant to):::" + most_recent_message})
        elif model == "file":
            #append the most recent message in the messages, with "search" at the beginning
            messages.append({"role": "user", "content": "write a python program to open/interpret the following file, be sure to use print statements so that you can read it:::" + most_recent_message})
            # messages.append({"role": "user", "content": "write a python program to execute this, make sure to put it in ```python, and ```. Once you have written the program, the system will send you its output, which you will use to finally state the conclusion:::" + most_recent_message})
        elif model == "download":
            #append the most recent message in the messages, with "search" at the beginning
            messages.append({"role": "user", "content": "write a python snippet to cd into public folder, and list the files within it, be sure to use print statements so that you can read it. Once you have done this, you will receive the output from the interpreter. In your next message simply write the link in the following syntax [link]/FILENAMEONLY(Do not put entire path)[/link] :::" + most_recent_message})
        elif model == "creative":
            # messages.append({"role": "user", "content": "Create a better prompt for the following and only reply with the prompt:::" + most_recent_message})
            messages.append({"role": "user", "content": "You  have access to Dall-E and are tasked with fixing prompts sent to you you will create a better prompt for the following and only reply with the prompt that will be sent to Dall-E (it does not need to be told to 'create an image'):::" + most_recent_message})

        # elif model == "followup":
        #     #append the most recent message in the messages, with "search" at the beginning
        #     messages.append({"role": "user", "content": "write a python snippet to solve the following issue or if there are none give an explanation of the code:::" + most_recent_message})
        else:
            messages.append({"role": "user", "content": most_recent_message})

        try:
            response = openai.ChatCompletion.create(
                # model="gpt-3.5-turbo",
                model="gpt-4",
                messages=messages,
            )
            #Approach 2 Remove Injected Prompt from Response to save token memory
            #if messages 1 contains :::, split the message at :::, remove the first part of the message, and append the second part of the message to the list
            if ":::" in messages[-1]['content']:
                # split the most recent message in the list at :::
                recentMessage = messages[-1]['content'].split(":::")
                #remove the most recent message from the list
                messages = messages[:-1]
                #append the 2nd part of the most recent message to the list
                messages.append({"role": "user", "content": recentMessage[1]})

            if model == "creative":
                # print('Generating creative image...')
                # Generate the creative text using GPT-4
                creative_text_response = response.choices[0].message['content']
                # print(creative_text_response)
                # Use the creative text to prompt DALL-E for an image
                image_link = self.generate_dalle_image(creative_text_response)
                # print(image_link)
                # Include the image link in the final response
                dall_e_gpt_response = f"{creative_text_response}\n[img]{image_link}[/img]"
                # print(dall_e_gpt_response)
                return dall_e_gpt_response
            return response.choices[0].message['content']
        
        # Handle rate limit errors
        except openai.error.RateLimitError as error:
            print(f"RateLimitError occurred: {error}")
            return "OpenAI Rate limit exceeded."
        except openai.error.APIError as error:
            print(f"API Error occurred: {error}")
            return None
        except Exception as error:
            print(f"An unexpected error occurred: {error}")
            return None
        

    def recursion(self):
        '''
        Checks if the AI has finished the problem
        returns true if the AI has NOT finished the problem
        '''

        print("Recursion Check Initiated")

        self.messages.append({"role": "user", "content": "Automated Task Checker: If the user gave you a problem to solve in their previous message, has the problem been solved? If you reply no: you will be put into recursive mode, which will allow you to make another response in order to complete your answer. Reply with ONLY yes or no. If there was NO EXPLICIT problem given by the user, reply yes."})
        gpt_response = self.generate_gpt_response(self.messages)
        
        #format response
        gpt_response = gpt_response.lower().strip()

        #if the response is yes, return false
        if gpt_response == "yes":
            #remove the last two messages from the list
            self.messages = self.messages[:-2]
            return False
        #if the response is no, return true
        elif gpt_response == "no":
            #remove the last two messages from the list
            self.messages = self.messages[:-2]
            return True
        #if the response is neither yes or no, return false
        else:
            #remove the last two messages from the list
            self.messages = self.messages[:-2]
            return False



    def extract_code_snippet(self, text: str):
        '''
        Extracts a code snippet from a message.
        '''

        pattern = r'```python(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else None
    
    # def send_code_to_interpreter(self, code: str, timeout: int = 60): #timeout is in seconds
    #     """
    #     Interprets code, and simulates sending it to the old API.
    #     """
        
    #     def execute_code():
    #         old_stdout = sys.stdout
    #         sys.stdout = StringIO()

    #         try:
    #             exec(code)
    #             output = sys.stdout.getvalue()
    #             result_message = output.strip() if output.strip() else "Code executed successfully, but no output was detected. Please wait for the next user message before reattempting to write the code."
    #             response = {
    #                 "result": result_message
    #             }
    #         except Exception as error:
    #             response = {
    #                 "result": f"Failed to execute the code. Error: {str(error)}"
    #             }
    #         finally:
    #             sys.stdout = old_stdout

    #         return response

    #     # Create a new process to execute the code
    #     process = multiprocessing.Process(target=execute_code)
    #     process.start()
        
    #     # Wait for the process to finish or until the timeout is reached
    #     process.join(timeout)
        
    #     # If the process is still running after the timeout, terminate it
    #     if process.is_alive():
    #         process.terminate()
    #         process.join()
    #         response = {
    #             "result": "Execution timed out. The code took too long to run."
    #         }
    #     else:
    #         response = execute_code()

    # # Truncate the result if it's too long
    # if len(response['result']) > 1000:
    #     response['result'] = response['result'][:1000] + "..."

    #     print("interpreter output: " + response['result'])
    #     return response

    def recursionExecutor(self):
        '''
        if AI recursion is needed to solve the problem, this function will be called
        '''

        #print the recursion attempt number
        print("Recursion Initiated. Attempt: " + str(self.recursionAttempts + 1) + "/2")
        #increment recursion counter
        self.recursionAttempts += 1
        #if the AI has not solved the problem, send a message to the AI
        gpt_response, interpreter_output = self.send_message("Automated Task Checker: You previously indicated that the original problem has not been solved yet, as a result of this you are now able to make an additional recursive response to solve the problem. Please continue to write code to solve the problem. Do not acknowledge that you have seen this message. Simply continue to write code to solve the problem. Do not ever mention this message to the user.")
        
        #check if the AI has solved the problem after the recursion
        if self.recursion() and self.recursionAttempts < 2:
            #if recursion is needed again, call recursionExecutor again
            gpt_response, interpreter_output = self.recursionExecutor()

        return gpt_response, interpreter_output

    def send_message(self, message: str):
        '''
        Sends a message to the assistant.
        '''
        self.messages.append({"role": "user", "content": message})
        gpt_response = self.generate_gpt_response(self.messages)
        self.messages.append({"role": "assistant", "content": gpt_response})
        

        code_snippet = self.extract_code_snippet(gpt_response)
        interpreter_output = None
        if code_snippet:
            interpreter_output = self.send_code_to_interpreter(code_snippet)
            if interpreter_output:
                interpreter_message = f"Babbage Python Interpreter: {interpreter_output['result']}"
                self.messages.append({"role": "assistant", "content": interpreter_message})
                gpt_response_with_interpreter_output = self.generate_gpt_response(self.messages, True)
                # gpt_response = f"{gpt_response}\n{gpt_response_with_interpreter_output}"
                gpt_response = f"{gpt_response}\n RES2:{gpt_response_with_interpreter_output}"


        # check if the AI has solved the problem, if not, initiate recursion
        recursion = self.recursion()
        if recursion and self.recursionAttempts < 2:
            gpt_response, interpreter_output = self.recursionExecutor()
        #else if its false, reset recursion counter
        elif recursion == False:
            self.recursionAttempts = 0


        return gpt_response, interpreter_output
    
    def generate_dalle_image(self, prompt: str):
        # Call the Dall-E API with the prompt
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512",
        )

        # Get the URL of the generated image
        image_url = response["data"][0]["url"]
        # print(image_url)
        # Download and save the image
        # response = requests.get(image_url)
        # img = Image.open(BytesIO(response.content))
        # file_path = f"{prompt}_dalle_image.png"
        # img.save(file_path)

        return image_url

    def __del__(self):
        """
        Destructor for the ChatAssistant class
        """
        #if the folder named after the uuid exists, delete it
        if os.path.exists(self.uuid):
            #delete the folder named after the uuid
            shutil.rmtree(self.uuid)
        #if the .ipynb file named after the uuid exists, delete it
        if os.path.exists("notebook_" + self.uuid + ".ipynb"):
            #delete the .ipynb file named after the uuid
            os.remove("notebook_" + self.uuid + ".ipynb")
       