#!/usr/bin/env python3
"""
Author : seong-eon Hwang (hseongeon@gmail.com)
Date   : 2025-06-18 ~

Purpose:
    WordForge는 사용자가 영어 단어를 직접 리스트에 추가하고, 원할 때마다 스스로 테스트를
    치를 수 있도록 도와주는 CLI 기반의 암기 도구입니다.
    단순히 무작위로 문제를 내는 것이 아니라, 우선순위 기반 시스템을 사용합니다.
    사용자가 이전에 정답을 맞혔는지 혹은 틀렸는지에 대한 이력을 기록하고,
    이 데이터를 바탕으로 자주 틀리거나 아직 익숙하지 않은 단어를 더 자주 노출시켜
    암기 효율을 극대화합니다.
"""

__version__ = "0.1.4"

from typing import List, Dict, Tuple, Union, cast
import readline  # type: ignore[unused-import] # noqa: F401
import json
import argparse
import datetime
import random
import logging
import unicodedata
import shutil
import os

from ansi import colorize, CYAN, BLUE, RED, BRIGHT_GREEN


# --- Type hint ---
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
    "숙어",
]

WORDS_FILE_NAME = "my_words.json"
BACKUP_DIRECTORY = "backup"


# --------------------------------------------------
def get_args():
    """커맨드 라인 인자를 얻는다."""

    parser = argparse.ArgumentParser(
        description=("퀴즈를 통해 영어 단어 암기를 도와주는 커맨드 라인 툴"),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("-b", "--backup", help="백업 모드 실행", action="store_true")
    parser.add_argument("-q", "--quiz", help="퀴즈 모드 실행", action="store_true")

    return parser.parse_args()


# --------------------------------------------------
def main():
    """main"""

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = get_args()
    if args.backup:
        execute_backup_mode()
        exit(0)
    if args.quiz:
        execute_quiz_mode()
    else:
        execute_input_mode()


# --------------------------------------------------
def copy_file_to_subdir(filename: str, dir_name: str):
    """지정된 디렉토리로 파일을 복사한다"""

    current_dir = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(current_dir, filename)
    target_dir = os.path.join(current_dir, dir_name)

    if not os.path.exists(target_dir):
        os.makedirs(target_dir)

    target_path = os.path.join(target_dir, filename)

    try:
        shutil.copy2(source_path, target_path)
        print("백업이 완료되었습니다.")
    except FileNotFoundError:
        print(f"'{filename}' 파일을 찾을 수 없습니다.")
    except Exception as e:
        print(f"시스템 오류: {e}")


def execute_backup_mode():
    """백업 모드 실행"""

    copy_file_to_subdir(WORDS_FILE_NAME, BACKUP_DIRECTORY)


# --------------------------------------------------
def execute_input_mode():
    """입력 모드 실행"""

    all_words: WordDataList = load_words_from_file(WORDS_FILE_NAME)
    words_dict: dict[str, WordEntry] = {}  ## Create a dict for O(1) lookups
    for entry in all_words:
        normalize_entry(entry)
        words_dict[cast(str, entry["word"])] = entry
    logging.info(f"불러온 단어 {len(all_words)}개")

    modified: bool = False
    while True:
        word = input("\n단어 입력 (예:'backfire'): ").strip()
        if not word:
            break

        entry: Union[WordEntry, None] = words_dict.get(word)
        if entry is None:
            new_word_entry: WordEntry = add_new_word_prompt(word)
            all_words.append(new_word_entry)
            words_dict[cast(str, new_word_entry["word"])] = new_word_entry
            modified = True
            print_entry_content(new_word_entry)
            logging.info(
                f"새 단어 추가 '{new_word_entry['word']}', "
                f"저장된 단어 {len(all_words)}개"
            )
        else:
            user_answer: str = should_edit(entry)
            if user_answer == "edit":
                modify_existing_word_prompt(entry)
                modified = True
                print_entry_content(entry)
                logging.info(f"수정된 단어 '{entry['word']}'")
            elif user_answer == "delete":
                all_words.remove(entry)
                words_dict.pop(cast(str, entry["word"]))
                modified = True
                logging.info(f"단어 삭제 '{entry['word']}'")

    if modified:
        save_words_to_file(WORDS_FILE_NAME, all_words)


# --------------------------------------------------
def execute_quiz_mode():
    """퀴즈 모드 실행"""

    all_words: WordDataList = load_words_from_file(WORDS_FILE_NAME)
    unselected_word_count: int = 0
    for entry in all_words:
        normalize_entry(entry)
        if entry["quiz_count"] == 0:
            unselected_word_count += 1
    logging.info(f"불러온 단어 {len(all_words)}개")
    logging.info(f"한 번도 출제되지 않은 단어 {unselected_word_count}개")
    session_quiz_count: int = 1

    while True:
        selected_words: WordDataList = select_words_for_quiz(all_words)
        logging.info("Word group chosen for quiz.")
        if not selected_words:
            logging.info("No words available for quiz.")
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
    JSON 파일에서 워드 데이터를 로드한다.
    파일이 없다면 빈 리스트를 만들고,
    로드하려는 파일이 유효하지 않다면 직접 수정할 수 있게 안내한다.
    """

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        logging.info(
            f"'{file_path}' 파일을 찾을 수 없습니다. 새로운 워드 데이터 파일을 "
            "생성합니다."
        )
        return []
    except json.JSONDecodeError:
        logging.error(
            f"'{file_path}', 유효하지 않은 JSON 포맷입니다. "
            "파일을 직접 확인하고 수정하세요."
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
        logging.info(f"'{file_path}' successfully saved.")
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
    normalize_entry(new_word_entry)
    return new_word_entry


# --------------------------------------------------
def modify_existing_word_prompt(entry: WordEntry):
    """Modify an existing word entry by re-entering its meanings and notes."""

    meanings: MeaningsList = input_meanings(cast(str, entry["word"]))
    notes_list: NotesList = input_notes()

    entry["meanings"] = meanings
    entry["notes"] = notes_list
    normalize_entry(entry)


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
            f"Word: {colorize(cast(str, entry['word']), CYAN)}"
            f"{' ' * 8}"
            f"(QC: {entry['quiz_count']}  ICC: {entry['incorrect_count']})"
            f"{' ' * 8}"
            f"{format_days_ago(cast(str, entry['last_quiz_date']))}"
        )

        # After recalling the meaning, the user simply presses Enter to continue.
        # No text input is required — the act of recalling the meaning is sufficient.
        user_answer = input(
            "Speak the word's meaning, then hit Enter to reveal the answer. (quit: q): "
        ).strip()
        if user_answer.lower() == "q":
            return session_quiz_count, False

        print_entry_content(entry)

        while True:
            user_answer = input(
                "Did you get the meaning correct? (1. Yes, 2. No, 3. Modify): "
            ).strip()
            if user_answer == "1":
                break
            elif user_answer == "2":
                incorrect_count = cast(int, entry["incorrect_count"])
                incorrect_count += 1
                entry["incorrect_count"] = incorrect_count
                break
            elif user_answer == "3":
                modify_existing_word_prompt(entry)
                logging.info(f"Modified existing word: {entry['word']}")
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
    Returns:
        - "first time" if the word has never been quizzed before,
        - "today" if the date is today,
        - "1 day ago" if it was yesterday,
        - "{n} days ago" for earlier dates.
    """

    if not date_str:
        return "first time"
    days_ago = (datetime.date.today() - datetime.date.fromisoformat(date_str)).days
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
            print("Input cannot be empty.")
            continue
        if not pos_choice_str.isdigit():
            print("Please enter a number.")
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

    print("\n--- Enter Notes (optional) ---")

    notes: NotesList = []
    while True:
        note = input("Enter a note: ").strip()
        if not note:
            break
        notes.append(note)
    return notes


# --------------------------------------------------
def print_entry_content(entry: WordEntry):
    """인자로 넘어 온 단어의 세부 내용(의미, 노트)을 출력한다."""

    meanings: List[str] = []
    for meaning, part_of_speech in cast(List[MeaningTuple], entry["meanings"]):
        meanings.append(colorize(meaning, BLUE) + "(" + part_of_speech + ")")
    print(", ".join(meanings))

    notes: List[str] = []
    for i, note in enumerate(cast(NotesList, entry["notes"])):
        notes.append("({}) ".format(i + 1) + colorize(note, BRIGHT_GREEN))
    if notes:
        print(" ".join(notes))


# --------------------------------------------------
def should_edit(entry: WordEntry) -> str:
    """
    인자로 넘어 온 단어의 디테일을 보여주고,
    유저에게 이 단어를 어떻게 할 것인지 물어본다.
    """

    print(f"단어: {entry['word']}")
    print_entry_content(entry)

    while True:
        user_answer = (
            input(
                colorize(
                    "이 단어를 어떻게 처리할까요? (edit, leave or delete): ",
                    RED,
                )
            )
            .strip()
            .lower()
        )
        if user_answer in ["edit", "leave", "delete"]:
            return user_answer


# --------------------------------------------------
def normalize(s: str) -> str:
    """일관된 유니코드 표현을 위해 문자열을 NFC 형식으로 정규화한다."""

    return unicodedata.normalize("NFC", s)


# --------------------------------------------------
def normalize_entry(entry: WordEntry):
    """normalize()를 사용하여 주어진 워드 엔트리의 모든 텍스트 필드를 정규화한다."""

    entry["word"] = normalize(cast(str, entry["word"]))

    meanings_list = cast(List[MeaningTuple], entry["meanings"])
    for i, (meaning, part_of_speech) in enumerate(meanings_list):
        meanings_list[i] = (normalize(meaning), normalize(part_of_speech))

    notes_list = cast(NotesList, entry["notes"])
    for i, note in enumerate(notes_list):
        notes_list[i] = normalize(note)


# --------------------------------------------------
if __name__ == "__main__":
    main()
