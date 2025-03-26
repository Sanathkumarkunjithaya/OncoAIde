function getCurrentTimestamp() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessageToChat(text, sender) {
    const timestamp = getCurrentTimestamp();
    const avatar = sender === 'user' ? 'static/img/onco.png' : 'static/img/favicon.png';

    const messageHTML = `
    <li class="chat-message ${sender}">
      <img src="${avatar}" alt="${sender} avatar" class="avatar" />
      <div class="message-content">${text}</div>
      <div class="timestamp">${timestamp}</div>
    </li>`;

    const chatContainer = $('.chat-messages');
    const previousScroll = chatContainer.scrollTop();
    const isUserScrolling = chatContainer[0].scrollHeight - chatContainer[0].scrollTop > chatContainer[0].clientHeight + 50;

    chatContainer.append(messageHTML);

    if (!isUserScrolling) {
        chatContainer.scrollTop(previousScroll);
    }

    setTimeout(() => {
        const chatMessages = document.querySelector(".chat-messages");
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }, 100);
}

// ... (keep other functions unchanged)

async function sendMessage() {
    const userInput = $('#msg_input').val().trim();
    if (!userInput) return;

    addMessageToChat(userInput, 'user');
    $('#msg_input').val('');
    $('#typing').show();

    try {
        console.log("🔹 Sending query:", userInput);
        let response = await fetch("http://127.0.0.1:8000/query", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query: userInput })
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP Error! Status: ${response.status} - ${errorText}`);
        }

        let data = await response.json();
        let botResponse = data.response
            ? formatResponse(data.response)
            : "⚠️ Unexpected response format.";
        addMessageToChat(botResponse, 'bot');
    } catch (error) {
        console.error("❌ Error fetching response:", error);
        addMessageToChat(`⚠️ Sorry, something went wrong: ${error.message}. Try again or specify a patient name (e.g., 'Tell me about Alice Johnson').`, 'bot');
    } finally {
        $('#typing').hide();
    }
}

// ... (rest of the code unchanged)
function formatResponse(response) {
    if (typeof response === "string") {
        return `<div class="response-box">${response.replace(/\n/g, "<br>")}</div>`;
    }

    let formattedText = `<div class="response-box">`;
    for (const key in response) {
        if (typeof response[key] === "object") {
            formattedText += `<h2>🔹 ${formatKeyName(key)}</h2><ul>`;
            for (const subKey in response[key]) {
                formattedText += `<li><b>${formatKeyName(subKey)}:</b> ${response[key][subKey]}</li>`;
            }
            formattedText += `</ul>`;
        } else {
            formattedText += `<h2>🔹 ${formatKeyName(key)}</h2><p>${response[key]}</p>`;
        }
    }
    formattedText += `</div>`;
    return formattedText;
}

function formatKeyName(key) {
    return key
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) => char.toUpperCase());
}

$('#send_button').on('click', sendMessage);
$('#msg_input').on('keypress', function (e) {
    if (e.key === 'Enter') sendMessage();
});

$('#theme_toggle').on('click', function () {
    const currentTheme = $('html').attr('data-theme');
    $('html').attr('data-theme', currentTheme === 'dark' ? 'light' : 'dark');
});

$(window).on('load', function () {
    addMessageToChat('👋 Welcome to OncoAide! How can I assist you today? Ask about "Alice Johnson." or another patient!"', 'bot');
});

document.getElementById('current-year').textContent = new Date().getFullYear();