const chatWindow = document.getElementById('chat-window');
const userList = document.getElementById('user-list');
const messageForm = document.getElementById('message-form')
const messageInput = document.getElementById('message-input')
const btnLogout = document.getElementById('logout')
const btnRegister = document.getElementById('register-btn')
const btnLogin = document.getElementById('login-btn')
const roomButtons = document.querySelectorAll('.room-btn');
const roomNameDisplay = document.getElementById('room-name');

// Глобальные переменные для хранения информации пользователя
let currentUserId = sessionStorage.getItem("currentUser");
let currentUsername = '';
let lastMessageTime = Date.now();

roomButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        switchRoom(btn.dataset.room);
    });
});

async function loadUsers()
{
    const currentRoom = sessionStorage.getItem("currentRoom") || "general";
    const response = await fetch(`http://127.0.0.1:8000/rooms/${currentRoom}/users`)
    const data = await response.json()
    renderUsers(data.active_users)
}

function renderUsers(data)
{
     userList.innerHTML = ''
     data.forEach( 
       u => {
              const li =  document.createElement("li")
              li.innerText = u.name
              userList.appendChild(li)
       }
     )
}

async function loadMessages()
{ 
  const currentRoom = sessionStorage.getItem("currentRoom") || "general";
    const response = await fetch(`http://127.0.0.1:8000/rooms/${currentRoom}/messages`)
    const data = await response.json()
    chatWindow.innerHTML = '';
    renderMessages(data)
}
function renderMessages(msgs)
{

    msgs.forEach(
        m=> {

            const messageDiv=document.createElement('div');
            let style_msg="other-message"
            if (m.user_id==sessionStorage.getItem("currentUser"))
                {style_msg="my-message"}
            messageDiv.classList.add('message',style_msg)
            messageDiv.innerHTML=`<div class="sender">${m.username}</div><div>${m.text}</div><div>${m.timestamp} </div>`
            chatWindow.appendChild(messageDiv)
            chatWindow.scrollTop = chatWindow.scrollHeight;
          } 
       )
}

async function sendMessage(e)
{
  e.preventDefault()
  
  // Проверяем, что пользователь залогинен
  const userId = sessionStorage.getItem("currentUser");
  if (!userId) {
    alert("Ошибка: вы не залогинены!");
    return;
  }
  
  // Проверяем, что сообщение не пусто
  if (!messageInput.value.trim()) {
    return;
  }
  
  const currentRoom = sessionStorage.getItem("currentRoom") || "general";
  const msg = {
    sender_id: userId,
    text: messageInput.value,
    room: currentRoom
  }
  
  const options = {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(msg)
  }

  try {
    const response = await fetch("http://localhost:8000/messages", options)
    
    if (response.ok) {
      const newMsg = await response.json();
      renderMessages([newMsg]);
      messageInput.value = "";
    } else {
      const error = await response.json();
      console.error("Ошибка при отправке сообщения:", error);
      alert(`Ошибка: ${error.detail || 'Не удалось отправить сообщение'}`);
    }
  } catch (error) {
    console.error('Сетевая ошибка при отправке сообщения:', error);
    alert('Ошибка сети. Проверьте соединение и попробуйте еще раз.');
  }
}


async function joinRoom(roomName, userId) {

        const response = await fetch(`http://localhost:8000/rooms/${roomName}/join`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        if (response.ok) {
            console.log(`Присоединился к комнате ${roomName}`);
            return true;
        } else {
            console.error('Не удалось присоединиться к комнате');
            return false;
        }
    
}

// Покинуть комнату
async function leaveRoom(roomName, userId) {
  
        const response = await fetch(`http://localhost:8000/rooms/${roomName}/leave`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: userId })
        });
        if (response.ok) {
            console.log(`Покинул комнату ${roomName}`);
            return true;
        } else {
            console.error('Не удалось покинуть комнату');
            return false;
        }
    
}

// Переключиться на другую комнату
async function switchRoom(roomName) {
    const currentRoom = sessionStorage.getItem("currentRoom") || "general";
    if (currentRoom === roomName) return; // Если уже в этой комнате, ничего не делаем

    // Покидаем текущую комнату
    await leaveRoom(currentRoom, currentUserId);

    // Присоединяемся к новой комнате
    const joined = await joinRoom(roomName, currentUserId);
    
    if (joined) {
         sessionStorage.setItem("currentRoom", roomName);
        roomNameDisplay.innerText = roomName;

        // Обновляем активные кнопки комнат
        roomButtons.forEach(btn => {
            if (btn.dataset.room === roomName) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Перезагружаем сообщения и пользователей
        await loadMessages();
        await loadUsers();
    }
}

async function registerUser(e)
{
  const user_input = document.querySelector("#register-block input")
  
  const msg = {username: user_input.value}
  const options = {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body:  JSON.stringify(msg)
  }
  const response = await fetch("http://localhost:8000/register",options)
  if(response.ok)
  {     
        const userData = await response.json();
        currentUserId = userData.id;
        currentUsername = userData.name;
        lastMessageTime = Date.now();
        await joinRoom('general', currentUserId);
        sessionStorage.setItem("currentUser",currentUserId)
        await loadUsers()
        await loadMessages();
        toggleChat()
        document.getElementById('register-error').innerText = '';
        user_input.value = '';
  }
  else{
     const error_p = document.getElementById("register-error")
     error_p.innerText = "Пользователь уже существует. Пожалуйста, выберите другое имя."
  }
}

function toggleChat()
{
    const chat_div = document.getElementById("chat")
    const login_register_block = document.getElementById('login-register-panel')
    const computedStyle = getComputedStyle(chat_div).display;
    if (computedStyle === "none") {
        chat_div.style.display = "block"
        login_register_block.style.display = "none"
    } else {
        chat_div.style.display = "none"
        login_register_block.style.display = "block"
    }
}

async function loginUser(e)
{
  const user_input = document.querySelector('#login-block input')
  
  const msg = {username: user_input.value}
  const options = {
    method: "POST",
    headers: { 'Content-Type': 'application/json' },
    body:  JSON.stringify(msg)
  }
  const response = await fetch("http://localhost:8000/login",options)
  if(response.ok)
  {
            const responseData = await response.json();
            const userData = responseData.user;
            currentUserId = userData.id;
            currentUsername = userData.name;
            lastMessageTime = Date.now();
            sessionStorage.setItem("currentUser",currentUserId)
            // Присоединяемся к комнате general
            await joinRoom('general', currentUserId);
            
            // Загружаем пользователей и сообщения
            await loadMessages();
            await loadUsers();
            
            // Переключаемся на чат
            toggleChat();
            
            document.getElementById('login-error').innerText = '';
            user_input.value = '';
  }
  else{
    const error_p = document.getElementById("login-error")
    error_p.innerText = "Пользователь не найден. Пожалуйста, зарегистрируйтесь."
  }
}

async function loadNewMessages()
{
    try {
        const currentRoom = sessionStorage.getItem("currentRoom") || "general";
        const response = await fetch(`http://localhost:8000/rooms/${currentRoom}/messages/poll?since=${lastMessageTime}`);
        if (response.ok) {
            const messages = await response.json();
            if (messages.length > 0) {
                renderMessages(messages);
                lastMessageTime = Date.now();
            }
        }
    } catch (error) {
        console.error('Ошибка при загрузке новых сообщений:', error);
    }
}

async function logoutUser()
{
    const currentRoom = sessionStorage.getItem("currentRoom") || "general";
    const currentUserId = sessionStorage.getItem("currentUser");
  
   // Покидаем текущую комнату
    await leaveRoom(currentRoom, currentUserId);
    sessionStorage.setItem("currentRoom", "general");
    // Очищаем поля чата
    chatWindow.innerHTML = '';
    userList.innerHTML = '';
    messageInput.value = '';
    // Переключаемся на экран логина
    toggleChat();
    sessionStorage.removeItem("currentUser")
}

function checkSession()
{
    const user = sessionStorage.getItem("currentUser")
    if(user)  {
        toggleChat()
    }

}

document.addEventListener('DOMContentLoaded', () => {
    checkSession();
});

loadUsers()
loadMessages()


messageForm.addEventListener("submit",sendMessage)
btnRegister.addEventListener("click",registerUser)
btnLogin.addEventListener("click",loginUser)
btnLogout.addEventListener("click",logoutUser)

setInterval(loadNewMessages, 10000)

