'use strict';

import {initializeApp} from "https://www.gstatic.com/firebasejs/9.22.2/firebase-app.js";
import {getAuth, createUserWithEmailAndPassword, signInWithEmailAndPassword, signOut} from "https://www.gstatic.com/firebasejs/9.22.2/firebase-auth.js"

var loginBox = document.getElementById("login-box");
var logoutBox = document.getElementById("logout-box");

const firebaseConfig = {
    apiKey: "AIzaSyA41CLcmuSbbRl8XFUryRaaz0sWPlvq02o",
    authDomain: "ssuriset-twitter-clone.firebaseapp.com",
    projectId: "ssuriset-twitter-clone",
    storageBucket: "ssuriset-twitter-clone.firebasestorage.app",
    messagingSenderId: "337714352354",
    appId: "1:337714352354:web:a48b89e44805b1f8288ebb",
    measurementId: "G-W5984QYHS5"
};

document.addEventListener('DOMContentLoaded', function () {
    const tweetTextArea = document.getElementById('tweet');
    const charCountSpan = document.getElementById('char-count');

    tweetTextArea.addEventListener('input', function () {
        const remaining = 140 - tweetTextArea.value.length;
        charCountSpan.textContent = remaining;
        if (remaining < 0) {
            tweetTextArea.value = tweetTextArea.value.substr(0, 140);
        }
    });
});

window.addEventListener("load", function() {
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    updateUI(document.cookie);

    if (loginBox) {
        document.getElementById("sign-up").addEventListener('click', function() {
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;

            createUserWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                const user = userCredential.user;
                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                    window.location = "/";
                });
            })
            .catch((error) => {
                console.log(error.code+error.message);
            })
        });
    }
    if (loginBox) {
        document.getElementById("login").addEventListener('click', function() {
            const email = document.getElementById("email").value;
            const password = document.getElementById("password").value;

            signInWithEmailAndPassword(auth, email, password)
            .then((userCredential) => {
                const user = userCredential.user;
                console.log("logged in");

                user.getIdToken().then((token) => {
                    document.cookie = "token=" + token + ";path=/;SameSite=Strict";
                    window.location = "/";
                });
            })
            .catch((error) => {
                console.log(error.code + error.message);
            })
        });
    }

    if (logoutBox) {
        document.getElementById("sign-out").addEventListener('click', function() {
            const auth = getAuth();
            signOut(auth).then(() => {
                console.log("Sign-out successful.");
                document.cookie = "token=;path=/;expires=Thu, 01 Jan 1970 00:00:00 GMT;SameSite=Strict";
                window.location = "/";
            }).catch((error) => {
                console.error("Sign-out error: ", error);
            });
        });       
    }
});

function updateUI(cookie) {
    var token = parseCookieToken(cookie);

    if (token.length > 0) {
        if (logoutBox) logoutBox.hidden = false;
        if (loginBox) loginBox.hidden = true;
    } else {
        if (logoutBox) logoutBox.hidden = true;
        if (loginBox) loginBox.hidden = false;
    }
}


function parseCookieToken(cookie) {
    var fun = "";
    var strings = cookie.split(';');

    for (let i = 0; i < strings.length; i++) {
        var temp = strings[i].split('=');
        if (temp[0] == "token") {
                fun = temp[1];
        }
    }
    return fun;
}