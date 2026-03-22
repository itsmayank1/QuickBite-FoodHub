// ================= GREETING =================
function getGreeting() {
    const hour = new Date().getHours();
    if (hour < 12) return "Good Morning ☀️";
    if (hour < 17) return "Good Afternoon 🌤️";
    if (hour < 21) return "Good Evening 🌙";
    return "Late night cravings? 😋";
}

const favFood = window.FAV_FOOD || "";

// ================= AUTO START MESSAGE (ONLY ONCE) =================
window.addEventListener("load", () => {

    const popup = document.getElementById("ai-popup");
    const box = document.getElementById("ai-messages");

    if (!popup || !box) return;

    popup.style.display = "block";

    addBotMessage(getGreeting() + ", welcome to QuickBite!");

    if (favFood && favFood !== "" && favFood !== "Cart Items") {
        addBotMessage("⭐ Your favourite food is " + favFood);
    } else {
        addBotMessage("🍕 Try our best seller pizza!");
    }

    addBotMessage(randomQuote());
});

// ================= QUOTES =================
const quotes = [
    "🍔 Good food = Good mood",
    "😋 Eat fresh, stay happy",
    "🔥 Today's special: Burger combo",
    "🍕 Pizza makes everything better",
    "💡 Tip: Use wallet for faster checkout"
];

function randomQuote(){
    return quotes[Math.floor(Math.random()*quotes.length)];
}

// ================= MESSAGE FUNCTIONS =================
function addBotMessage(text){
    const box = document.getElementById("ai-messages");
    const msg = document.createElement("div");
    msg.className = "ai-msg bot";
    msg.innerText = text;
    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
}

function addUserMessage(text){
    const box = document.getElementById("ai-messages");
    const msg = document.createElement("div");
    msg.className = "ai-msg user";
    msg.innerText = text;
    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
}

// ================= TOGGLE =================
function toggleAI() {
    const popup = document.getElementById("ai-popup");
    popup.style.display = popup.style.display === "block" ? "none" : "block";
}

function closeAI() {
    document.getElementById("ai-popup").style.display = "none";
}

// ================= SEND MESSAGE =================
function sendMessage() {

    const input = document.getElementById("ai-input");
    const text = input.value.trim();
    if (!text) return;

    addUserMessage(text);

    const lower = text.toLowerCase();

    let reply = "Try asking about favourite, quote or recommendation 😉";

    if (lower.includes("hi") || lower.includes("hello")) {
        reply = getGreeting();
    }
    else if (lower.includes("fav")) {
        reply = favFood ? 
            "Your favourite food is " + favFood : 
            "You haven't ordered yet.";
    }
    else if (lower.includes("recommend")) {
        reply = "I recommend Burger 🍔";
    }
    else if (lower.includes("wallet")) {
        reply = "You can pay using wallet 💰";
    }
    else if (lower.includes("quote")) {
        reply = randomQuote();
    }

    setTimeout(() => {
        addBotMessage(reply);
    }, 500);

    input.value = "";
}