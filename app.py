'''
GPT-X
'''
import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from ChatAssistant import ChatAssistant
from globals import assistants

def save_file_to_disk(file, file_name, uuid):
    '''
    Save a file to disk
    '''

    # If no directory for the instance  exists, create one
    if not os.path.exists(uuid):
        os.makedirs(uuid)

    # destination_path = os.path.join("public", file_name)  # Create the destination path
    destination_path = os.path.join(uuid, file_name)  # Create the destination path

    # Save the file to the destination
    file.save(destination_path)

    # If file is successfully saved to disk
    if os.path.exists(destination_path):
        assistant = assistants.get(uuid)
        assistant.add_file_to_list(destination_path)
        print("File saved to disk successfully!")

        #if a \ is in the destination path (so that GPT cd's into the correct directory when the files are moved to temp dir)
        if '\\' in destination_path:
            #save the last part of the file name
            destination_path = destination_path.split('\\')[-1]

        #This will be implemented later
        # #if the destination_path ends in .jpg, .jpeg, .png, .gif, .svg, .ico, .jfif, .pjpeg, or.pjp
        # if destination_path.endswith(('.jpg', '.jpeg', '.png', '.gif', '.svg', '.ico', '.jfif', '.pjpeg', '.pjp')):
        #     #add [img] and [/img] tags to the destination path
        #     destination_path = '[img]/' + destination_path + '[/img]'

        # Create a response json object
        response = {
            "result": f"File {destination_path} saved to disk successfully!",
        }
        return response
    else:
        print("Failed to save the file to disk.")
        # Create a response json object
        response = {
            "result": f"Failed to save the file {file_name} to disk.",
        }
        return response

def extract_code_snippet(gpt_repsonse):
    '''
    Extract any code snippet from the GPT-3 response and remove it from the response string
    '''
    pattern = r'```python(.*?)```'
    match = re.search(pattern, gpt_repsonse, re.DOTALL)
    code_snippet = match.group(1).strip() if match else None
    return code_snippet

def remove_code_snippet(gpt_response):
    '''
    Remove any code snippet from the GPT-3 response
    '''
    gpt_response = re.sub(r"```python(.*?)```", "", gpt_response, flags=re.DOTALL)
    return gpt_response

def handle_response_with_two_parts(gpt_response):
    '''
    If the response contains "RES2:", split it into two parts and return both parts
    '''
    gpt_response2 = gpt_response.split("RES2:")[1]
    gpt_response = gpt_response.split("RES2:")[0]
    gpt_response2 = remove_code_snippet(gpt_response2)

    return gpt_response, gpt_response2

# Initialize Flask app
app = Flask(__name__)
cors = CORS(app, resources={r"*": {"origins": "*"}})

# @app.route("/save_api_key", methods=["POST"])
# def save_api_key():
#     '''
#     Save the OpenAI API key in the global openai_api_key variable
#     '''

#     global openai_api_key
#     openai_api_key = request.json["apiKey"]
#     return jsonify({"status": "success"})

@app.route("/save_uuid", methods=["POST"])
# def save_uuid():
#     '''
#     Save the uuid of the user in the global assistants dictionary
#     each uuid is associated with a ChatAssistant object
#     '''

#     uuid = request.json["uuid"]
    
#     if uuid not in assistants:
#         assistants[uuid] = ChatAssistant(openai_api_key, uuid)
#     print (assistants)
#     return jsonify({"status": "success"})
def save_uuid():
    '''
    Save the uuid of the user in the global assistants dictionary
    each uuid is associated with a ChatAssistant object
    '''

    uuid = request.json["uuid"]
    api_key = request.json["apiKey"]  # Extract the API key from the request

    if uuid not in assistants:
        assistants[uuid] = ChatAssistant(api_key, uuid)
    else:
        # Update the existing ChatAssistant object with the new API key
        assistants[uuid].api_key = api_key
    print(assistants)
    return jsonify({"status": "success"})

@app.route("/send_message", methods=["POST"])
def send_message():
    '''
    Send a message to the assistant and return the response
    '''
    # Extract the uuid from the POST request and retrieve the AI assistant object
    uuid = request.form["uuid"]
    user_message = request.form["message"]

    # Send the message to the AI assistant and retrieve a GPT-3 response and interpreter output
    assistant = assistants.get(uuid)
    gpt_response, interpreter_output = assistant.send_message(user_message)

    # Extract any code snippet
    code_snippet = extract_code_snippet(gpt_response)
    gpt_response = remove_code_snippet(gpt_response)

    # Return the response
    if "RES2:" not in gpt_response:
        return jsonify({"gpt_response": gpt_response,
                        "interpreter_output": interpreter_output,
                        "code_snippet": code_snippet})
    else:
        gpt_response, gpt_response2 = handle_response_with_two_parts(gpt_response)
        return jsonify({"gpt_response": gpt_response,
                        "gpt_response2": gpt_response2,
                        "interpreter_output": interpreter_output,
                        "code_snippet": code_snippet})

@app.route("/send_file", methods=["POST"])
def send_file():
    '''
    Send a file to the assistant and return the response
    '''
    # Extract the uuid from the POST request and retrieve the AI assistant object
    uuid = request.form["uuid"] 
    assistant = assistants.get(uuid)

    # Check if a file was uploaded
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Please attach a file to the request."}), 400

    # Get the uploaded file
    file = request.files["file"]
    file_name = secure_filename(file.filename)

    # Send the file to the AI assistant API and retrieve a response
    # response = save_file_to_disk(file, file_name)
    response = save_file_to_disk(file, file_name, uuid)

    # Send the response from the AI assistant API to the AI assistant and retrieve a GPT-3 response and interpreter output
    gpt_response, interpreter_output = assistant.send_message(response['result'])

    # Extract any code snippet
    code_snippet = extract_code_snippet(gpt_response)
    gpt_response = remove_code_snippet(gpt_response)

    # Return the response
    if "RES2:" not in gpt_response:
        return jsonify({"system": response['result'],
                        "response": gpt_response,
                        "interpreter_output": interpreter_output,
                        "code_snippet": code_snippet})
    else:
        gpt_response, gpt_response2 = handle_response_with_two_parts(gpt_response)
        return jsonify({"system": response['result'],
                        "response": gpt_response,
                        "response2": gpt_response2,
                        "interpreter_output": interpreter_output,
                        "code_snippet": code_snippet})
    
@app.route("/delete_chat", methods=["POST"])
def delete_chat():
    '''
    Delete the chat history of the user
    '''
    #delete the chatassistant object from the dictionary
    uuid = request.json["uuid"]
    assistant = assistants.get(uuid)
    del assistant

    #call the destructor
    del assistants[uuid]
    if uuid not in assistants:
        print("Chat history deleted successfully!")
        return jsonify({"status": "success"})
    else:
        print("Failed to delete chat history.")
        return jsonify({"status": "failed"})

if __name__ == "__main__":
    # app.run(debug=True)
    app.run(port=5001)
