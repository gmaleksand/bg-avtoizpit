

import json
import random
import tkinter as tk
from tkinter import font
from PIL import Image, ImageTk
import os
import cv2
from ffpyplayer.player import MediaPlayer
import requests
from io import BytesIO

class QuizApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Driving Quiz")
        with open("questions.json", "r") as f:
            self.questions = json.load(f)
        self.weights_path = "weights.csv"
        self.load_weights()
        self.current_question = None
        self.video_player = None

        # Create a canvas and a scrollbar
        self.canvas = tk.Canvas(root)
        self.scrollbar = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Bind mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Set up fonts
        self.default_font = font.nametofont("TkDefaultFont")
        self.default_font.configure(size=12)
        self.question_font = font.Font(family="Helvetica", size=16, weight="bold")

        # Create widgets inside the scrollable frame
        self.question_label = tk.Label(self.scrollable_frame, text="", wraplength=500, font=self.question_font)
        self.question_label.pack(pady=10)

        self.media_label = tk.Label(self.scrollable_frame)
        self.media_label.pack(pady=10)

        self.answer_frame = tk.Frame(self.scrollable_frame)
        self.answer_frame.pack(pady=10)

        self.answer_vars = []
        self.answer_buttons = []

        self.input_certainty = tk.StringVar(value='0.5')
        self.certainty_entry = tk.Entry(self.scrollable_frame, textvariable=self.input_certainty, font=self.default_font)
        self.certainty_entry.pack(pady=10)

        self.submit_button = tk.Button(self.scrollable_frame, text="Submit", command=self.check_answer, font=self.default_font)
        self.submit_button.pack(pady=10)

        self.result_label = tk.Label(self.scrollable_frame, text="", font=self.default_font)
        self.result_label.pack(pady=10)

        self.next_button = tk.Button(self.scrollable_frame, text="Next Question", command=self.next_question, font=self.default_font)
        self.next_button.pack(pady=10)

        # Pack the canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.questions_solved = 0
        self.questions_solved_correctly = 0
        self.next_question()

    def load_weights(self):
        if os.path.exists(self.weights_path):
            with open(self.weights_path, 'r') as f:
                self.weights = [float(line.strip()) for line in f.readlines()]
            if len(self.weights) != len(self.questions):
                print(f"Warning: Mismatch between number of weights ({len(self.weights)}) and questions ({len(self.questions)}). Recreating weights file.")
                self.create_default_weights()
        else:
            print(f"Warning: '{self.weights_path}' not found. Creating a new one with default weights.")
            self.create_default_weights()

    def create_default_weights(self):
        num_questions = len(self.questions)
        self.weights = [1.0] * num_questions
        self.save_weights()

    def save_weights(self):
        with open(self.weights_path, 'w') as f:
            for weight in self.weights:
                f.write(f"{weight}\n")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def next_question(self):
        self.result_label.config(text="")
        self.submit_button.config(state=tk.NORMAL)
        if self.video_player:
            self.video_player.close_player()
            self.video_player = None

        for widget in self.answer_frame.winfo_children():
            widget.destroy()
        self.answer_vars.clear()
        self.answer_buttons.clear()

        question_index = random.choices(range(len(self.questions)), weights=self.weights, k=1)[0]
        self.current_question = self.questions[question_index]
        self.current_question['index'] = question_index
        self.display_question()

    def display_question(self):
        question_text = self.current_question["q"]
        num_correct = self.current_question["correct_answers_count"]
        self.question_label.config(text=f"{question_text}\n(Correct answers: {num_correct})")

        video_url = self.current_question["video"]
        image_path = self.current_question["img"]

        if video_url is not None:
            self.play_video_from_url(video_url)
        elif image_path is not None and os.path.exists(image_path):
            self.display_image(image_path)
        else:
            self.media_label.config(image="")
            self.media_label.image = None

        self.display_answers()

    def display_image(self, path):
        img = Image.open(path)
        img.thumbnail((400, 400))
        photo = ImageTk.PhotoImage(img)
        self.media_label.config(image=photo)
        self.media_label.image = photo

    def play_video_from_url(self, url):
        url_local = "videos/" + url.replace('/','-')
        if os.path.exists(url_local):
            play_video(url_local)
        else:
            try:
                response = requests.get(url, stream=True)
                response.raise_for_status()
                # Save video content to a temporary file
                with open(url_local, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                self.play_video(url_local)
            except requests.exceptions.RequestException as e:
                print(f"Error fetching video from {url}: {e}")

    def play_video(self, path):
        cap = cv2.VideoCapture(path)
        self.video_player = MediaPlayer(path)

        def stream():
            ret, frame = cap.read()
            if ret:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame)
                img.thumbnail((800, 800))
                photo = ImageTk.PhotoImage(image=img)
                self.media_label.config(image=photo)
                self.media_label.image = photo
                self.root.after(30, stream)
            else:
                cap.release()

        stream()

    def display_answers(self):
        answers = self.get_answers()
        random.shuffle(answers)

        for i, (answer_text, is_correct) in enumerate(answers):
            var = tk.BooleanVar()
            self.answer_vars.append((var, is_correct))
            if isinstance(answer_text, str) and answer_text.endswith('.png'):
                if os.path.exists(answer_text):
                    img = Image.open(answer_text)
                    img.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(img)
                    button = tk.Checkbutton(self.answer_frame, image=photo, variable=var)
                    button.image = photo
                else:
                    button = tk.Checkbutton(self.answer_frame, text="Image not found", variable=var, wraplength=400, font=self.default_font)
            elif isinstance(answer_text, str):
                button = tk.Checkbutton(self.answer_frame, text=answer_text, variable=var, wraplength=400, font=self.default_font)
            else: # Should not happen with the new structure
                button = tk.Checkbutton(self.answer_frame, image=answer_text, variable=var)
                button.image = answer_text
            button.pack(anchor="w")
            self.answer_buttons.append(button)

    def get_answers(self):
        answers = []
        for answer_text, is_correct in self.current_question["answers"].items():
            answers.append((answer_text, bool(is_correct)))
        return answers

    def get_correct_answers(self):
        correct_answers = []
        for answer_text, is_correct in self.current_question["answers"].items():
            if is_correct:
                correct_answers.append(answer_text)
        return correct_answers

    def check_answer(self):
        self.submit_button.config(state=tk.DISABLED)
        all_correct = True
        selected_answers_texts = []
        for i, (var, is_correct) in enumerate(self.answer_vars):
            if var.get():
                selected_answers_texts.append(self.answer_buttons[i].cget("text"))
            if var.get() != is_correct:
                all_correct = False

        if all_correct and len(selected_answers_texts) == len(self.get_correct_answers()):
            self.result_label.config(text="Correct!", fg="green")
            question_index = self.current_question['index']
            self.weights[question_index] *= float(self.certainty_entry.get())
            self.save_weights()
            self.questions_solved_correctly += 1
        else:
            correct_answers_text = self.get_correct_answers_display()
            self.result_label.config(text=f"Wrong! Correct answers are:\n{correct_answers_text}", fg="red")

        self.questions_solved += 1
        print(str(self.questions_solved_correctly) + '/' + str(self.questions_solved))

    def get_correct_answers_display(self):
        return "\n".join(self.get_correct_answers())

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1920x1080")
    app = QuizApp(root)
    root.mainloop()

