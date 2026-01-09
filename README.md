# 💬 DelDevCode

Just a chat app I’ve been focusing on lately. Feel free to use it and customize it for you and your friends! (I'll be making it easier to configure over time).

---

## 🌍 Language / Langue
> [!NOTE]  
> The project is currently **French-only**. I am planning to add more languages later.  
> **Contribution:** If you want to have fun translating the app or creating a language config system, feel free to open a **Pull Request**! I'd be happy to merge your work.

---

## 🚀 Getting Started

Follow these steps to get your own instance of DelDevCode up and running:

### 1. Download the Project
Go to the **[Releases](https://github.com/Tatoudm/deldevcode/releases)** page and download the latest `.zip` file. Extract it to your desired folder.

### 2. Configuration (`.env`)
The app needs some information to run. 
* Locate the file named `.env.example`.
* Open it and fill in your details (MongoDB URI, Port, etc.).
* **Important:** Rename the file to exactly `.env`.

### 3. Database Requirement (MongoDB)
> [!IMPORTANT]  
> This project currently **only works with MongoDB**. It is hardcoded for it, so it won't work with other databases without modifying the source code. Support for other databases might come in the future!

### 4. Run the App
Make sure you have Python installed, then run:
```bash
python app.py
