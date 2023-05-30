//index.js
$(document).ready(function() {
    $("#chat-form").on("submit", function(e) {
        e.preventDefault();
        const message = $("#user-input").val();
        if (message.trim() !== "") {
            appendMessage("You", message);
            $("#user-input").val("");
            $.post("/send_message", {message: message}, function(data) {
                appendMessage("Assistant", data.response);
                if (data.code_snippet) {                            
                    updateCodeSnippet(data.code_snippet);
                }
                if (data.interpreter_output) {
                    updateInterpreterOutput(data.interpreter_output.result);
                }
            });
        }
    });
});
function uploadFile() {
    const fileInput = document.getElementById("file-input");
    if (fileInput.files.length === 0) {
        return;
    }

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    $.ajax({
        url: "/send_file",
        type: "POST",
        data: formData,
        processData: false,
        contentType: false,
        success: function(data) {
            // appendMessage("Interpreter", JSON.stringify(data.result));
            appendMessage("Interpreter", JSON.stringify(data.result));
            // appendMessage("Assistant", JSON.stringify(data.completion));
        },
        error: function(xhr, status, error) {
            appendMessage("Interpreter", "Error: " + xhr.responseText);
        }
    });
}


function appendMessage(sender, message) {
    const interpreterOutputRegex = /The interpreter's output is: (.*)/;
    const codeSnippetRegex = /(```python[\s\S]*?```)/;
    let senderClass = '';

    const interpreterOutputMatch = message.match(interpreterOutputRegex);
    const codeSnippetMatch = message.match(codeSnippetRegex);

    if (sender === 'Assistant') {
        senderClass = 'assistant-message';
    } else if (sender === 'You') {
        senderClass = 'user-message';
    } else if (sender === 'Interpreter') {
        senderClass = 'interpreter-message';
    }

    if (sender === 'Assistant' && message.includes('RES2:')) {
        const res2Split = message.split('RES2:');
        const beforeRes2 = res2Split[0];
        const afterRes2 = res2Split[1] || '';

        message = `<span class="assistant-message-before-res2">${beforeRes2}</span><span class="assistant-message-after-res2">${afterRes2}</span>`;
    }

    if (interpreterOutputMatch) {
        const interpreterOutput = interpreterOutputMatch[1];
        const responseWithoutInterpreterOutput = message.replace(interpreterOutputRegex, '').trim();

        if (codeSnippetMatch) {
            responseWithoutInterpreterOutput = responseWithoutInterpreterOutput.replace(codeSnippetRegex, '').trim();
        }
        $("#chat-area").append(`<p class="${senderClass}"><b>${sender}:</b> ${responseWithoutInterpreterOutput}</p>`);
        $("#interpreter-area").append(`${interpreterOutput}\n`);
        $("#interpreter-output").html(`<pre>${interpreterOutput}</pre>`);  // Update the interpreter output div
    } else {
        if (codeSnippetMatch) {
            message = message.replace(codeSnippetRegex, '').trim();
        }
        $("#chat-area").append(`<p class="${senderClass}"><b>${sender}:</b> ${message}</p>`);
    }

    $("#chat-area").scrollTop($("#chat-area")[0].scrollHeight);
    $("#interpreter-area").scrollTop($("#interpreter-area")[0].scrollHeight);
}

let previousCodeSnippets = [];
let currentSnippetIndex = -1;

function updateCodeSnippet(code, output) {
    // Push the current code snippet and its output to the list of previous code snippets
    previousCodeSnippets.push({code: code, output: output});
    currentSnippetIndex = previousCodeSnippets.length - 1;

    // Update the interpreter-area div content
    $("#interpreter-area").html(`<pre><code class="language-python">${code}</code></pre>`);
    $("#interpreter-area").scrollTop($("#interpreter-area")[0].scrollHeight);
    setTimeout(function() {
        Prism.highlightAll(); // Call Prism.highlightAll() after the content has been updated
    }, 0);
}

function updateInterpreterOutput(output) {
    // Update the interpreter-output div content
    $("#interpreter-output").html(`<pre><code class="language-bash">user@gpt-x:~$\n${output}</code></pre>`);
    $("#interpreter-output").scrollTop($("#interpreter-output")[0].scrollHeight);
    setTimeout(function() {
        Prism.highlightAll(); // Call Prism.highlightAll() after the content has been updated
    }, 0);

    // Save the output along with the current code snippet
    if (currentSnippetIndex >= 0) {
        previousCodeSnippets[currentSnippetIndex].output = output;
    }
}

function goToPreviousCode() {
    if (currentSnippetIndex > 0) {
        currentSnippetIndex--;
        const snippet = previousCodeSnippets[currentSnippetIndex];
        $("#interpreter-area").html(`<pre><code class="language-python">${snippet.code}</code></pre>`);
        $("#interpreter-output").html(`<pre><code class="language-bash">user@gpt-x:~$\n${snippet.output}</code></pre>`);
        Prism.highlightAll();
    }
}

function goToNextCode() {
    if (currentSnippetIndex < previousCodeSnippets.length - 1) {
        currentSnippetIndex++;
        const snippet = previousCodeSnippets[currentSnippetIndex];
        $("#interpreter-area").html(`<pre><code class="language-python">${snippet.code}</code></pre>`);
        $("#interpreter-output").html(`<pre><code class="language-bash">user@gpt-x:~$\n${snippet.output}</code></pre>`);
        Prism.highlightAll();
    }
}
let previousFolderState = new Map();

async function checkFolderUpdates(folderHandle) {
  const currentFolderState = new Map();

  for await (const entry of folderHandle.values()) {
    const file = await entry.getFile();
    const lastModified = new Date(file.lastModified);
    currentFolderState.set(file.name, lastModified);

    if (!previousFolderState.has(file.name) || previousFolderState.get(file.name) < lastModified) {
      appendSystemMessage("", file);
    }
  }

  previousFolderState = currentFolderState;
}
  

function monitorUploadsFolder() {
  if ("showDirectoryPicker" in window) {
    (async () => {
      try {
        const folderHandle = await window.showDirectoryPicker();
        if (folderHandle.name === "uploads") {
          setInterval(async () => {
            await checkFolderUpdates(folderHandle);
          }, 5000); // Check for updates every 5 seconds
        }
      } catch (error) {
        console.error("Error monitoring folder:", error);
      }
    })();
  } else {
    alert("Your browser does not support the FileSystem API.");
  }
}
function appendSystemMessage(message, file) {
    const messageElement = $("<div class='system-message'></div>");
    messageElement.text(message);
    $("#chat-area").append(messageElement);
  
    if (file && (file.type.startsWith("image/") || file.type === "application/pdf")) {
      const fileReader = new FileReader();
      fileReader.onload = function(e) {
        if (file.type.startsWith("image/")) {
          const imageElement = $("<img class='uploaded-image' />");
          imageElement.attr("src", e.target.result);
          imageElement.attr("width", "50%");
          imageElement.attr("height", "50%");
          //center the image
          imageElement.css("text-align", "center");

          $("#chat-area").append(imageElement);
        } else if (file.type === "application/pdf") {
          const pdfElement = $("<embed class='uploaded-pdf' type='application/pdf'>");
          pdfElement.attr("src", e.target.result);
          pdfElement.attr("width", "50%");
          pdfElement.attr("height", "50%");
          //center the pdf
          pdfElement.css("text-align", "center");
          $("#chat-area").append(pdfElement);
        }
      };
      fileReader.readAsDataURL(file);
    }
  
    $("#chat-area").scrollTop($("#chat-area")[0].scrollHeight);
  }
  