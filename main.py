from tkinter import *
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sqlite3
import json
import argparse
import re
from typing import Tuple, List, TextIO, Dict
from googletrans import Translator
import os
import spacy
from nltk import Tree
from nltk.treeprettyprinter import TreePrettyPrinter


class TranslatorGUI:
    def __init__(self, master):
        self.master = master
        master.title("Translator")
        master.geometry("640x420")
        self.file = None
        self.choose_mode()

    def ask_for_file(self):
        self.file = filedialog.askopenfilename(initialdir=os.path.dirname(__file__),
                                               filetypes=(
                                                   ("Text files", "*.txt"),
                                                   ("Json files", "*.json"),
                                                   ("all files", "*.*")
                                               ))

    def clear_frame(self):
        for widget in self.master.winfo_children():
            widget.destroy()
            widget.pack_forget()

    def choose_mode(self):
        self.clear_frame()
        translate_mode_btn = Button(self.master, text="Translate", command=self.translate_mode)
        fill_mode_btn = Button(self.master, text="Fill", command=self.fill_mode)
        translate_mode_btn.pack()
        fill_mode_btn.pack()

    def translate_mode(self):
        try:
            self.ask_for_file()
            self.clear_frame()
            text, api, db, trees = translate_file(self.file)

            tab_control = ttk.Notebook(self.master, width=640, height=360)

            tab1 = ttk.Frame(tab_control)
            tab1_text = scrolledtext.ScrolledText(tab1)
            tab1_text.insert(INSERT, text)
            tab1_text.pack()
            tab_control.add(tab1, text='Translated text')

            def format_dict(_dict):
                _text = ''
                for _item, _freq in _dict.items():
                    _text += f'{_item}: {_freq};\n'
                return _text

            tab2 = ttk.Frame(tab_control)
            tab2_text = scrolledtext.ScrolledText(tab2)
            tab2_text.insert(INSERT, format_dict(api))
            tab2_text.pack()
            tab_control.add(tab2, text='Word frequencies (API)')

            tab3 = ttk.Frame(tab_control)
            tab3_text = scrolledtext.ScrolledText(tab3)
            tab3_text.insert(INSERT, format_dict(db))
            tab3_text.pack()
            tab_control.add(tab3, text='Word frequencies (DB)')

            def show_tree(_tree):
                for widget in tab4.winfo_children():
                    widget.destroy()
                    widget.pack_forget()
                _txt = scrolledtext.ScrolledText(tab4)
                _txt.insert(INSERT, _tree)
                _txt.pack()

            tab4 = ttk.Frame(tab_control)
            for sent, tree in trees.items():
                btn = Button(tab4, text=sent, command=lambda: show_tree(tree))
                btn.pack()
            tab_control.add(tab4, text='Tree')

            tab_control.pack(expand=1, fill='both')

            back_btn = Button(self.master, text='Back', command=self.choose_mode)
            back_btn.pack()
        except Exception:
            raise
            self.choose_mode()
            messagebox.showerror('Error', 'Try to chose another file')

    def fill_mode(self):
        self.ask_for_file()
        parse_file(self.file)
        messagebox.showinfo('Filling', 'Filled successfully')


def resolve_lang(lang: str) -> str:
    if lang == 'en':
        return 'Eng'
    elif lang == 'ru':
        return 'Rus'
    elif lang == 'de':
        return 'Deu'


def commit_word(source: str, destination: str, languages: Tuple[str, str] = ('en', 'de')):
    source_lang, destination_lang = languages
    source_lang = resolve_lang(source_lang)
    destination_lang = resolve_lang(destination_lang)

    source_field = 'Wrd' + source_lang
    destination_field = 'Wrd' + destination_lang

    cursor.execute(f"SELECT IDWrd FROM Dict WHERE {source_field} = ? AND {destination_field} = ?",
                   [source, destination])
    if cursor.fetchone() is not None:
        return

    cur_id = cursor.execute("SELECT MAX(IDWrd) FROM Dict").fetchone()[0] + 1
    cursor.execute(
        f"INSERT INTO Dict (IDWrd, {source_field}, {destination_field}) VALUES ({cur_id}, '{source}', '{destination}')")
    conn.commit()


def commit_func(source: str, destination: str, positions: List[Tuple[str, str]],
                languages: Tuple[str, str] = ('en', 'de')):
    source_lang, destination_lang = languages
    source_lang = resolve_lang(source_lang)
    destination_lang = resolve_lang(destination_lang)

    source_field = 'FTxt' + source_lang
    destination_field = 'FTxt' + destination_lang

    cursor.execute(f"SELECT IDFunc FROM Func WHERE {source_field} = ? AND {destination_field} = ?",
                   [source, destination])

    if cursor.fetchone() is not None:
        return

    cur_id = cursor.execute("SELECT MAX(IDFunc) FROM Func").fetchone()[0] + 1
    cursor.execute(
        f"INSERT INTO Func (IDFunc, {source_field}, {destination_field}) VALUES ({cur_id}, '{source}', '{destination}')")
    conn.commit()

    source_field = 'Pos' + source_lang
    destination_field = 'Pos' + destination_lang
    cur_id = cursor.execute("SELECT MAX(ID) FROM Pos").fetchone()[0] + 1
    for position in positions:
        source_pos, destination_pos = position
        cursor.execute(
            f"INSERT INTO Pos (ID, {source_field}, {destination_field}) VALUES ({cur_id}, '{source_pos}', '{destination_pos}')")
        conn.commit()
        cur_id += 1


def parse_json(file: TextIO):
    data = json.load(file)
    words = data['words']
    funcs = data['functions']

    for word in words:
        src = word['src']
        dest = word['dest']
        lang = word['lang']
        commit_word(src, dest, languages=(lang['src'], lang['dest']))

    for func in funcs:
        src = func['src']
        dest = func['dest']
        pos = func['pos']
        lang = func['lang']
        commit_func(src, dest, pos, languages=(lang['src'], lang['dest']))


def parse_legacy(file: TextIO):
    data = file.read()
    commands = data.split('\n\n')
    for command in commands:
        com, *args = command.split('\n')
        if com.lower() == 'word':
            src_word, dest_words, langs = args
            src_lang, dest_lang = langs.split('->')
            for word in dest_words.split(';'):
                commit_word(src_word, word, (src_lang, dest_lang))
        if com.lower() == 'func':
            src_func, dest_func, pos, langs = args
            src_lang, dest_lang = langs.split('->')
            pos = [tuple(p.split('->')) for p in pos.split(';')]
            commit_func(src_func, dest_func, pos, (src_lang, dest_lang))


def parse_file(path_to_file: str):
    if os.path.isfile(path_to_file):
        with open(path_to_file, 'r') as f:
            if path_to_file.endswith('.txt'):
                parse_legacy(f)
            elif path_to_file.endswith('.json'):
                parse_json(f)


def gen_regexps(languages: Tuple[str, str] = ('en', 'de')) -> List[Tuple[str, str]]:
    source_lang, destination_lang = languages
    source_lang = resolve_lang(source_lang)
    destination_lang = resolve_lang(destination_lang)

    words = cursor.execute(f"SELECT IDWrd, {'Wrd' + source_lang}, {'Wrd' + destination_lang} FROM Dict ").fetchall()
    funcs = cursor.execute(f"SELECT IDFunc, {'FTxt' + source_lang}, {'FTxt' + destination_lang} FROM Func ").fetchall()
    func_words = cursor.execute("SELECT IDWrd, IDFunc FROM Func_Wrd ").fetchall()
    positions = cursor.execute(f"SELECT IDFunc, {'Pos' + source_lang}, {'Pos' + destination_lang} FROM Pos ").fetchall()

    words = {wrd_id: tuple(wrds) for wrd_id, *wrds in words}
    funcs = {func_id: tuple(func) for func_id, *func in funcs}
    new_func_words = {}
    for word_id, func_id in func_words:
        if func_id in new_func_words:
            new_func_words[func_id].append(word_id)
        else:
            new_func_words[func_id] = [word_id]
    func_words = new_func_words
    del new_func_words
    new_positions = {}
    for position in positions:
        func_id = position[0]
        if func_id in new_positions:
            new_positions[func_id].append(position[1:])
        else:
            new_positions[func_id] = [position[1:]]
    positions = new_positions
    del new_positions

    regexp_to_func = []
    for func_id, func in funcs.items():
        try:
            cur_func_words = [words[word_id] for word_id in func_words[func_id]]
            cur_positions = {src: dest for src, dest in positions[func_id]}
        except KeyError:
            continue
        cur_source_func, cur_destination_func = func
        for index, position in enumerate(re.findall('|'.join(cur_positions.keys()), cur_source_func)):
            cur_source_func = cur_source_func.replace(position,
                                                      f'({"|".join({word[0].strip() for word in cur_func_words})})')
            cur_destination_func = cur_destination_func.replace(cur_positions[position], '{%d}' % index)
        cur_source_func = '(' + cur_source_func + ')'
        regexp_to_func.append((cur_source_func, cur_destination_func))

    return regexp_to_func


def translate_file(path_to_file: str, src: str = 'en', dest: str = 'de'):
    if os.path.isfile(path_to_file):
        with open(path_to_file, 'r') as f:
            return translate(f.read(), src, dest)


def tok_format(tok):
    return "_".join([tok.orth_, tok.tag_])


def to_nltk_tree(node):
    if node.n_lefts + node.n_rights > 0:
        return Tree(tok_format(node), [to_nltk_tree(child) for child in node.children])
    else:
        return tok_format(node)


def translate(text: str, src: str = 'en', dest: str = 'de') -> Tuple[
    str, Dict[str, int], Dict[str, int], Dict[str, str]]:
    text = text.lower()
    src_nlp = spacy.load(src)
    nlp_text = src_nlp(text)

    sent_trees = {sent.text: TreePrettyPrinter(to_nltk_tree(sent.root), None, ()).text() for sent in nlp_text.sents}

    regexps = gen_regexps(languages=(src, dest))
    excluded = {}

    def exclude_from_translating(sent, text_):
        if len(excluded.keys()) == 0:
            pk = 0
        else:
            pk = max(excluded.keys()) + 1
        text_ = text_.replace(sent, '{%d}' % pk)
        excluded[pk] = sent
        return text_

    def replace_excluded(text_):
        return text_.format(*[i for _, i in sorted(excluded.items())])

    words = cursor.execute(f"SELECT {'Wrd' + resolve_lang(src)}, {'Wrd' + resolve_lang(dest)} FROM Dict;").fetchall()
    words = {src_word: dest_word for src_word, dest_word in words}

    regexps_freq = {}
    for item in regexps:
        regexp, func = item
        regexps_freq[regexp] = 0
        for res in re.findall(regexp.lower(), text):
            regexps_freq[regexp] += 1
            to_replace, *to_replace_words = res
            to_replace_words = [words[word].lower() for word in to_replace_words]
            text = text.replace(to_replace, func.format(*to_replace_words))
            text = exclude_from_translating(func.format(*to_replace_words), text)

    nlp_text = src_nlp(text)
    word_freq = {}
    for sent in nlp_text.sents:
        for word in sent:
            if word in word_freq:
                word_freq[word.text] += 1
            else:
                word_freq[word.text] = 0

    translator = Translator()
    text = translator.translate(text, src=src, dest=dest).text
    text = replace_excluded(text)
    return (text, dict(sorted(word_freq.items(), key=lambda item: item[1], reverse=True)), dict(
        sorted(regexps_freq.items(), key=lambda item: item[1], reverse=True)), sent_trees)


def init_argument_parser():
    parser = argparse.ArgumentParser()
    ui_group = parser.add_mutually_exclusive_group()
    ui_group.add_argument('-G', '--gui', action='store_true',
                          help='''start program with GUI (if include this argument all
                           other will be ignored) [using this mode by default]''',
                          default=True)
    ui_group.add_argument('-C', '--cli', action='store_true', help='start program with CLI', default=False)

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument('-F', '--fill', action='store_true',
                              help='''indicates that the file contains information
                               to fill the database''',
                              default=False)
    action_group.add_argument('-T', '--translate', action='store_true',
                              help='indicates that the file contains text to translate [using this mode by default]',
                              default=True)
    parser.add_argument('--file', type=str, help='specify path to file')

    return parser


def main():
    parser = init_argument_parser()
    args = parser.parse_args()
    if args.cli and args.file is None:
        parser.error('--file argument is required when CLI mode is enabled')

    if args.cli:
        if os.path.isfile(args.file):
            if args.fill:
                parse_file(args.file)
            elif args.translate:
                text, _, _, _ = translate_file(args.file)
                print(text)
    elif args.gui:
        root = Tk()
        gui = TranslatorGUI(root)
        root.mainloop()


if __name__ == '__main__':
    conn = sqlite3.connect('PEREV.sqlite')
    cursor = conn.cursor()
    main()
