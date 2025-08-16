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
            "A CLI tool to help memorize English vocabularythrough self quizzes"
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
    words_dict: dict[str, WordEntry] = {}  ## O(1) 검색을 위한 dict 생성
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
            new_word_entry: Union[WordEntry, None] = add_new_word_prompt(word)
            if new_word_entry is None:
                break
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
        session_quiz_count, should_quit = show_quizzes(
            selected_words, session_quiz_count
        )
        if not should_quit:
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
            f"Failed to load '{file_path}': invalid JSON format. \
                      Please check or fix the file manually"
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
            # Dump the list of dictionaries to JSON format
            json.dump(words_data, fh, ensure_ascii=False, indent=4)
        logging.info(f"'{file_path}' successfully saved")
    except IOError as e:
        logging.error(f"Could not save to '{file_path}'. {e}")


# --------------------------------------------------
def add_new_word_prompt(new_word: str) -> Union[WordEntry, None]:
    """
    Prompts the user to enter new word details with numbered part-of-speech options.
    Returns a WordEntry dictionary or None if cancelled.
    """

    meanings_list: MeaningsList = []
    print("\n--- Enter Meanings ---")
    while True:
        meaning = input(
            f"Enter meaning for {new_word} (e.g., '역효과가 나다'): "
        ).strip()
        if not meaning:
            if not meanings_list:
                print("Meaning cannot be empty. Please try again.")
                continue
            else:
                break

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
            selected = POS_OPTIONS[pos_choice_int - 1]
            break

        meanings_list.append((meaning, selected))

    notes_list: NotesList = []
    print("\n--- Enter Notes (Optional) ---")
    while True:
        note = input("Enter a note: ").strip()
        if not note:  # 그냥 엔터 치면 종료
            break
        notes_list.append(note)

    new_word_entry: WordEntry = {
        "word": new_word,
        "meanings": meanings_list,
        "notes": notes_list,
        "created_date": datetime.date.today().isoformat(),
        "quiz_count": 0,
        "incorrect_count": 0,
        "last_quiz_date": "",
    }
    return new_word_entry


# --------------------------------------------------
def modify_existing_word_prompt(entry: WordEntry):
    meanings_list: MeaningsList = []
    print("\n--- Enter Meanings ---")
    while True:
        meaning = input(
            f"Enter meaning for {entry['word']} (e.g., '역효과가 나다'): "
        ).strip()
        if not meaning:
            if not meanings_list:
                print("Meaning cannot be empty. Please try again.")
                continue
            else:
                break

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
            selected = POS_OPTIONS[pos_choice_int - 1]
            break

        meanings_list.append((meaning, selected))

    notes_list: NotesList = []
    print("\n--- Enter Notes (Optional) ---")
    while True:
        note = input("Enter a note: ").strip()
        if not note:  # 그냥 엔터 치면 종료
            break
        notes_list.append(note)

    entry["meanings"] = meanings_list
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

    # 모든 단어의 priority_score 계산
    # score = quiz_count - incorrect_count
    # 이 score가 낮을수록 더 자주 출제되어야 합니다.
    priority_scores: List[int] = [
        cast(int, entry["quiz_count"]) - cast(int, entry["incorrect_count"])
        for entry in words_data
    ]

    # 최대 priority_score를 찾아 가중치 계산에 사용
    # 모든 단어의 score가 0일 수도 있으므로, max_score를 적절히 처리해야 합니다.
    # 만약 단어가 하나도 없거나, 모든 score가 0이면 max_score_val은 0이 될 수 있습니다.
    max_score_val = max(priority_scores) if priority_scores else 0

    # score를 random.choices()에 사용할 weight로 변환
    # weight가 높을수록 뽑힐 확률이 높습니다.
    # (max_score_val + 1) - score를 하면, score가 낮을수록 weight가 높아집니다.
    weights: List[int] = [(max_score_val + 1) - score for score in priority_scores]

    # random.choices()를 사용하여 단어 추출
    # 단어 목록의 총 개수보다 num_to_select가 크면 오류가 나므로, min 함수 사용
    num_actual_select = min(num_to_select, len(words_data))

    # choices 함수는 중복을 허용하여 뽑을 수 있습니다.
    selected_words_data_with_duplicates = random.choices(
        words_data, weights=weights, k=num_actual_select
    )
    deduplicated_words_data = deduplicate_words(selected_words_data_with_duplicates)

    return deduplicated_words_data


# --------------------------------------------------
def deduplicate_words(words_data: WordDataList) -> WordDataList:
    """
    random.choices() 함수는 중복 추출을 허용하기 때문에 중복을 직접 제거하여야 한다.
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
        created_date = datetime.date.fromisoformat(cast(str, entry["created_date"]))
        days_ago = (datetime.date.today() - created_date).days
        if days_ago == 0:
            data_label = "today"
        elif days_ago == 1:
            data_label = "1 day ago"
        else:
            data_label = f"{days_ago} days ago"
        print(f"--- Quiz ({session_quiz_count}) ---")
        print(
            f"Word: {colorize(cast(str, entry['word']), BRIGHT_CYAN)}\
                (QC: {entry['quiz_count']}  ICC: {entry['incorrect_count']})\
                    {data_label}"
        )

        # 유저가 단어의 뜻을 말한 후 엔터를 누르면 넘어간다.
        # 내용을 입력할 필요가 없다. 유저가 뜻을 상기시키기는 행위로 충분하다.
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
if __name__ == "__main__":
    main()
