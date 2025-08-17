#!/usr/bin/env python3
"""
Author : seong-eon Hwang (hseongeon@gmail.com)
Date   : 2025-06-18

Purpose:
    WordForge is a command-line tool that helps users memorize English
    vocabulary by allowing them to add words to a list and quiz themselves
    at any time.
"""

__version__ = "0.1.2"

from typing import List, Dict, Tuple, Union, cast
from ansi import colorize, BRIGHT_CYAN, BRIGHT_BLUE
import json
import argparse
import datetime
import random
import logging


# --- type hint ---
MeaningTuple = Tuple[str, str]
MeaningsList = List[MeaningTuple]
NotesList = List[str]

WordEntry = Dict[str, Union[str, MeaningsList, NotesList, int]]
WordDataList = List[WordEntry]

POS_OPTIONS = [
    "동사",
    "명사",
    "형용사",
    "부사",
    "전치사",
    "접속사",
    "대명사",
    "감탄사",
    "관사",
]

WORDS_FILE_NAME = "my_words.json"


# --------------------------------------------------
def get_args():
    """Get command-line arguments"""

    parser = argparse.ArgumentParser(
        description=(
            "A CLI tool to help memorize English vocabulary through self-quizzes"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-q", "--quiz", help="Execute the quiz mode", action="store_true"
    )

    return parser.parse_args()


# --------------------------------------------------
def main():
    """main"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = get_args()
    if args.quiz:
        execute_quiz_mode()
    else:
        execute_input_mode()


# --------------------------------------------------
def execute_input_mode():
    """Execute input mode"""

    all_words: WordDataList = load_words_from_file(WORDS_FILE_NAME)
    words_dict: dict[str, WordEntry] = {}  ## Create a dict for O(1) lookups
    for entry in all_words:
        words_dict[cast(str, entry["word"])] = entry
    logging.info(f"Loaded word count: {len(all_words)}")

    modified: bool = False
    while True:
        word = input("\nEnter the word (e.g., 'backfire'): ").strip()
        if not word:
            break

        entry: Union[WordEntry, None] = words_dict.get(word)
        if entry is None:
            new_word_entry: WordEntry = add_new_word_prompt(word)
            all_words.append(new_word_entry)
            words_dict[cast(str, new_word_entry["word"])] = new_word_entry
            modified = True
            logging.info(
                f"Added new word: {new_word_entry['word']}, "
                f"Current word count: {len(all_words)}"
            )
        else:
            modify_existing_word_prompt(entry)
            modified = True
            logging.info(
                f"Modified existing word: {entry['word']}, "
                f"Current word count: {len(all_words)}"
            )

    if modified:
        save_words_to_file(WORDS_FILE_NAME, all_words)


# --------------------------------------------------
def execute_quiz_mode():
    """Execute quiz mode"""

    all_words: WordDataList = load_words_from_file(WORDS_FILE_NAME)
    logging.info(f"Loaded word count: {len(all_words)}")
    session_quiz_count: int = 1

    while True:
        selected_words: WordDataList = select_words_for_quiz(all_words)
        logging.info("Word group chosen for quiz")
        if not selected_words:
            logging.info("No words available for quiz")
            break
        session_quiz_count, keep_running = show_quizzes(
            selected_words, session_quiz_count
        )
        if not keep_running:
            save_words_to_file(WORDS_FILE_NAME, all_words)
            break


# --------------------------------------------------
def load_words_from_file(file_path: str) -> WordDataList:
    """
    Loads word data from a JSON file.
    Initializes an empty list if the file is not found or is invalid JSON.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logging.info(f"'{file_path}' not found. Creating a new word list")
        return []
    except json.JSONDecodeError:
        logging.error(
            f"Failed to load '{file_path}': invalid JSON format. "
            "Please check or fix the file manually"
        )
        exit(1)


# --------------------------------------------------
def save_words_to_file(file_path: str, words_data: WordDataList):
    """
    Saves the current word data list to a JSON file.
    This will overwrite the existing file.
    """

    try:
        with open(file_path, "w", encoding="utf-8") as fh:
            json.dump(words_data, fh, ensure_ascii=False, indent=4)
        logging.info(f"'{file_path}' successfully saved")
    except IOError as e:
        logging.error(f"Could not save to '{file_path}'. {e}")


# --------------------------------------------------
def add_new_word_prompt(new_word: str) -> WordEntry:
    """Prompts the user to enter meanings and notes for a new word."""

    meanings: MeaningsList = input_meanings(new_word)
    notes: NotesList = input_notes()

    new_word_entry: WordEntry = {
        "word": new_word,
        "meanings": meanings,
        "notes": notes,
        "created_date": datetime.date.today().isoformat(),
        "quiz_count": 0,
        "incorrect_count": 0,
        "last_quiz_date": "",
    }
    return new_word_entry


# --------------------------------------------------
def modify_existing_word_prompt(entry: WordEntry):
    """Modify an existing word entry by re-entering its meanings and notes."""

    meanings: MeaningsList = input_meanings(cast(str, entry["word"]))
    notes_list: NotesList = input_notes()

    entry["meanings"] = meanings
    entry["notes"] = notes_list

    return entry


# --------------------------------------------------
def select_words_for_quiz(
    words_data: WordDataList, num_to_select: int = 30
) -> WordDataList:
    """
    Selects a specified number of words for a quiz based on their calculated
    priority scores. Words with lower (quiz_count - incorrect_count) scores will have
    a higher probability of being selected.
    """

    if not words_data:
        return []

    priority_scores: List[int] = [
        cast(int, entry["quiz_count"]) - cast(int, entry["incorrect_count"])
        for entry in words_data
    ]

    # Find the maximum priority_score for use in weight calculation.
    # If there are no words or all scores are 0, max_score_val may be 0.
    max_score_val = max(priority_scores) if priority_scores else 0

    # Convert the score into a weight for use in random.choices().
    # The higher the weight, the greater the probability of being selected.
    weights: List[int] = [(max_score_val + 1) - score for score in priority_scores]

    # Use the min function because an error occurs if num_to_select exceeds
    # the total number.
    num_actual_select = min(num_to_select, len(words_data))

    # random.choices() allows duplicates.
    selected_words_data_with_duplicates = random.choices(
        words_data, weights=weights, k=num_actual_select
    )

    # Duplicates must be removed manually.
    deduplicated_words_data = deduplicate_words(selected_words_data_with_duplicates)

    return deduplicated_words_data


# --------------------------------------------------
def deduplicate_words(words_data: WordDataList) -> WordDataList:
    """
    Remove duplicate word entries from the list using object identity.
    Only entries that point to the exact same object instance are removed.
    This ensures faster comparison than equality checks.
    """

    deduplicated: WordDataList = []
    for entry in words_data:
        if not any(entry is e for e in deduplicated):
            deduplicated.append(entry)

    return deduplicated


# --------------------------------------------------
def show_quizzes(
    quiz_words_data: WordDataList, session_quiz_count: int
) -> tuple[int, bool]:
    """
    Shows quizzes to the user, updates word stats, and handles user input.
    """

    for entry in quiz_words_data:
        print(f"--- Quiz ({session_quiz_count}) ---")
        print(
            f"Word: {colorize(cast(str, entry['word']), BRIGHT_CYAN)}"
            f"{' ' * 8}"
            f"(QC: {entry['quiz_count']}  ICC: {entry['incorrect_count']})"
            f"{' ' * 8}"
            f"{format_days_ago(cast(str, entry['created_date']))}"
        )

        # After recalling the meaning, the user simply presses Enter to continue.
        # No text input is required — the act of recalling the meaning is sufficient.
        user_answer = input(
            "Speak the word's meaning, then hit Enter to reveal the answer. (quit: q): "
        ).strip()
        if user_answer.lower() == "q":
            return session_quiz_count, False

        meanings: List[str] = []
        for meaning, part_of_speech in cast(List[MeaningTuple], entry["meanings"]):
            meanings.append(colorize(meaning, BRIGHT_BLUE) + "(" + part_of_speech + ")")
        print(", ".join(meanings))

        notes: List[str] = []
        for i, note in enumerate(cast(NotesList, entry["notes"])):
            notes.append("({}) ".format(i + 1) + note)
        if notes:
            print(" ".join(notes))

        while True:
            user_answer = input(
                "Did you get the meaning correct? (1. Yes, 2. No): "
            ).strip()
            if user_answer == "1":
                break
            elif user_answer == "2":
                incorrect_count = cast(int, entry["incorrect_count"])
                incorrect_count += 1
                entry["incorrect_count"] = incorrect_count
                break
            else:
                continue

        quiz_count = cast(int, entry["quiz_count"])
        quiz_count += 1
        entry["quiz_count"] = quiz_count
        entry["last_quiz_date"] = datetime.date.today().isoformat()

        session_quiz_count += 1

    return session_quiz_count, True


# --------------------------------------------------
def format_days_ago(date_str: str) -> str:
    """
    Convert an ISO-formatted date string into a human-readable relative date label.
    Returns "today" if the date is today, "1 day ago" if it was yesterday,
    or "{n} days ago" for earlier dates.
    """

    created_date = datetime.date.fromisoformat(date_str)
    days_ago = (datetime.date.today() - created_date).days
    if days_ago == 0:
        return "today"
    if days_ago == 1:
        return "1 day ago"
    return f"{days_ago} days ago"


# --------------------------------------------------
def select_pos() -> str:
    """
    Prompt the user to select a part of speech from the predefined POS_OPTIONS list.
    The user must enter a valid number corresponding to an option. Returns the
    selected part of speech as a string.
    """

    for i, pos_name in enumerate(POS_OPTIONS):
        print(f"{i + 1}. {pos_name}")

    while True:
        pos_choice_str = input("Select part of speech by number: ").strip()
        if not pos_choice_str:
            print("Input cannot be empty. Please enter a number.")
            continue

        pos_choice_int = int(pos_choice_str)
        if not (1 <= pos_choice_int <= len(POS_OPTIONS)):
            print("Invalid number. Please choose from the options.")
            continue
        selected: str = POS_OPTIONS[pos_choice_int - 1]
        return selected


# --------------------------------------------------
def input_meanings(word: str) -> MeaningsList:
    """
    Prompt the user to enter one or more meanings for a given word,
    each with a selected part of speech. Continues until at least
    one meaning is provided and the user enters an empty input.
    """

    print("\n--- Enter Meanings ---")

    meanings: MeaningsList = []
    while True:
        meaning = input(f"Enter meaning for '{word}' (e.g., '역효과가 나다'): ").strip()
        if not meaning:
            if not meanings:
                print("Meaning cannot be empty. Please try again.")
                continue
            break
        meanings.append((meaning, select_pos()))
    return meanings


# --------------------------------------------------
def input_notes() -> NotesList:
    """
    Prompt the user to enter optional notes for a word.
    The user can input multiple notes, and pressing Enter
    without input ends the note entry process.
    """

    print("\n--- Enter Notes ---")

    notes: NotesList = []
    while True:
        note = input("Enter a note (Optional): ").strip()
        if not note:
            break
        notes.append(note)
    return notes


# --------------------------------------------------
if __name__ == "__main__":
    main()
