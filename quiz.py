

import pandas as pd
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
        self.questions_df = pd.read_excel("all_questions.xlsx")
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
            self.weights = pd.read_csv(self.weights_path, header=None, dtype=float).squeeze("columns")
            if len(self.weights) != len(self.questions_df):
                print(f"Warning: Mismatch between number of weights ({len(self.weights)}) and questions ({len(self.questions_df)}). Recreating weights file.")
                self.create_default_weights()
        else:
            print(f"Warning: '{self.weights_path}' not found. Creating a new one with default weights.")
            self.create_default_weights()

    def create_default_weights(self):
        num_questions = len(self.questions_df)
        self.weights = pd.Series([1.0] * num_questions)
        self.save_weights()

    def save_weights(self):
        self.weights.to_csv(self.weights_path, index=False, header=False)

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

        self.current_question = self.questions_df.sample(weights=self.weights).iloc[0]
        self.display_question()

    def display_question(self):
        question_text = self.current_question["question"]
        num_correct = self.current_question["number of correct answers"]
        self.question_label.config(text=f"{question_text}\n(Correct answers: {num_correct})")

        video_url = self.current_question["video-url"]
        image_path = self.current_question["img-path"]

        if pd.notna(video_url):
            self.play_video_from_url(video_url)
        elif pd.notna(image_path) and os.path.exists(image_path):
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

        for i, (answer_text, is_correct, original_index) in enumerate(answers):
            var = tk.BooleanVar()
            self.answer_vars.append((var, is_correct, original_index))
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
        correct_indices = self.get_correct_answers()
        
        for i, col in enumerate(['a', 'b', 'c', 'd']):
            answer_text = self.current_question[col]
            is_correct = self.current_question[f'{col}_correct'] == 1
            
            if pd.notna(answer_text):
                answers.append((answer_text, is_correct, i + 1))
        return answers

    def get_correct_answers(self):
        correct_answers = []
        for i, col in enumerate(['a', 'b', 'c', 'd']):
            if self.current_question[f'{col}_correct'] == 1:
                correct_answers.append(i + 1)
        return correct_answers

    def check_answer(self):
        self.submit_button.config(state=tk.DISABLED)
        all_correct = True
        selected_answers = []
        for i, (var, is_correct, original_index) in enumerate(self.answer_vars):
            if var.get():
                selected_answers.append(original_index)
            if var.get() != is_correct:
                all_correct = False

        if all_correct and len(selected_answers) == len(self.get_correct_answers()):
            self.result_label.config(text="Correct!", fg="green")
            question_index = self.current_question.name
            self.weights.loc[question_index] *= float(self.certainty_entry.get())
            self.save_weights()
            self.questions_solved_correctly += 1
        else:
            correct_answers_text = self.get_correct_answers_display()
            self.result_label.config(text=f"Wrong! Correct answers are:\n{correct_answers_text}", fg="red")

        self.questions_solved += 1
        print(str(self.questions_solved_correctly) + '/' + str(self.questions_solved))

    def get_correct_answers_display(self):
        correct_answers_text = []
        answers = self.get_answers()
        correct_indices = self.get_correct_answers()

        for answer_text, is_correct, original_index in answers:
            if original_index in correct_indices:
                if isinstance(answer_text, str) and not answer_text.endswith('.png'):
                    correct_answers_text.append(answer_text)
                else:
                    correct_answers_text.append(f"Answer {original_index} (Image)")
        return "\n".join(correct_answers_text)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1920x1080")
    app = QuizApp(root)
    root.mainloop()

