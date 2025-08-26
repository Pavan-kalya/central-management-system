async function sendPrompt() {
    const prompt = document.getElementById("prompt").value;
    const responseBox = document.getElementById("response");

    responseBox.innerHTML = "⏳ Thinking...";

    const res = await fetch("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt })
    });

    const data = await res.json();
    if (data.response) {
        responseBox.innerHTML = data.response;
    } else {
        responseBox.innerHTML = "⚠️ Error: " + data.error;
    }
}
