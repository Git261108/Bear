# -*- coding: utf-8 -*-
"""数据库模块：SQLite 建表与常用操作"""
import sqlite3
import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'jiakao.db')


def get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS subjects (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        name     TEXT NOT NULL UNIQUE,          -- 科目名称，如 科目一
        question_count INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS questions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        chapter     TEXT DEFAULT '',               -- 章节/分类
        qtype       TEXT NOT NULL CHECK(qtype IN ('单选','多选','判断')),
        question    TEXT NOT NULL,
        options     TEXT NOT NULL,                 -- JSON 数组，如 ["对","错"]
        answer      TEXT NOT NULL,                 -- 单选/判断: "A"；多选: "ABD"
        explanation TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_q_subject ON questions(subject_id);

    CREATE TABLE IF NOT EXISTS wrong_book (
        question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
        wrong_count INTEGER NOT NULL DEFAULT 1,
        last_wrong  TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS favorites (
        question_id INTEGER PRIMARY KEY REFERENCES questions(id) ON DELETE CASCADE,
        add_time    TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS practice_progress (   -- 顺序练习进度
        subject_id  INTEGER PRIMARY KEY REFERENCES subjects(id) ON DELETE CASCADE,
        last_index  INTEGER NOT NULL DEFAULT 0      -- 已练到的第 N 题（从 1 开始）
    );

    CREATE TABLE IF NOT EXISTS subject_settings (    -- 各科目练习设置
        subject_id       INTEGER PRIMARY KEY REFERENCES subjects(id) ON DELETE CASCADE,
        random_count     INTEGER NOT NULL DEFAULT 0, -- 随机练习题数（0=全部）
        wrong_exam_count INTEGER NOT NULL DEFAULT 0  -- 错题本考试题数（0=全部）
    );

    CREATE TABLE IF NOT EXISTS answer_records (     -- 答题记录，用于统计
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
        is_correct  INTEGER NOT NULL,               -- 1 对 0 错
        source      TEXT DEFAULT 'practice',        -- practice / exam / wrong / favorite
        answer_time TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE TABLE IF NOT EXISTS exam_records (       -- 模拟考试成绩
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
        score       INTEGER NOT NULL,
        total       INTEGER NOT NULL,
        correct     INTEGER NOT NULL,
        passed      INTEGER NOT NULL,
        duration    INTEGER NOT NULL,               -- 用时（秒）
        exam_time   TEXT DEFAULT (datetime('now','localtime'))
    );
    """)
    conn.commit()
    conn.close()


def refresh_subject_counts():
    """导入题库后刷新每个科目的题目总数"""
    conn = get_conn()
    conn.execute("""
        UPDATE subjects SET question_count =
            (SELECT COUNT(*) FROM questions q WHERE q.subject_id = subjects.id)
    """)
    conn.commit()
    conn.close()


# ---------------- 科目 ----------------
def list_subjects():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM subjects ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_subject(name):
    conn = get_conn()
    cur = conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return cur.lastrowid


def find_subject_id(name):
    conn = get_conn()
    r = conn.execute("SELECT id FROM subjects WHERE name = ?", (name,)).fetchone()
    conn.close()
    return r['id'] if r else None


def rename_subject(subject_id, name):
    conn = get_conn()
    conn.execute("UPDATE subjects SET name = ? WHERE id = ?", (name, subject_id))
    conn.commit()
    conn.close()


def delete_subject(subject_id):
    conn = get_conn()
    conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()


# ---------------- 题目 ----------------
def get_questions(subject_id, ids=None, shuffle=False):
    conn = get_conn()
    sql = "SELECT * FROM questions WHERE subject_id = ?"
    params = [subject_id]
    if ids:
        marks = ','.join('?' * len(ids))
        sql += f" AND id IN ({marks})"
        params += list(ids)
    sql += " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    result = []
    for r in rows:
        q = dict(r)
        q['options'] = json.loads(q['options'])
        result.append(q)
    if shuffle:
        import random
        random.shuffle(result)
    return result


def get_question(qid):
    conn = get_conn()
    r = conn.execute("SELECT * FROM questions WHERE id = ?", (qid,)).fetchone()
    conn.close()
    if r:
        q = dict(r)
        q['options'] = json.loads(q['options'])
        return q
    return None


def clear_subject_questions(subject_id):
    conn = get_conn()
    conn.execute("DELETE FROM questions WHERE subject_id = ?", (subject_id,))
    conn.commit()
    conn.close()


# ---------------- 错题本 / 收藏 ----------------
def add_wrong(qid):
    conn = get_conn()
    conn.execute("""
        INSERT INTO wrong_book(question_id, wrong_count)
        VALUES (?, 1)
        ON CONFLICT(question_id) DO UPDATE SET
            wrong_count = wrong_count + 1,
            last_wrong  = datetime('now','localtime')
    """, (qid,))
    conn.commit()
    conn.close()


def remove_wrong(qid):
    conn = get_conn()
    conn.execute("DELETE FROM wrong_book WHERE question_id = ?", (qid,))
    conn.commit()
    conn.close()


def get_wrong_ids(subject_id=None):
    conn = get_conn()
    if subject_id:
        rows = conn.execute("""
            SELECT w.question_id FROM wrong_book w
            JOIN questions q ON q.id = w.question_id
            WHERE q.subject_id = ?
            ORDER BY w.last_wrong DESC
        """, (subject_id,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT question_id FROM wrong_book ORDER BY last_wrong DESC").fetchall()
    conn.close()
    return [r['question_id'] for r in rows]


def get_settings(subject_id):
    """返回 {random_count, wrong_exam_count, progress}"""
    conn = get_conn()
    r = conn.execute("SELECT * FROM subject_settings WHERE subject_id = ?",
                     (subject_id,)).fetchone()
    p = conn.execute("SELECT last_index FROM practice_progress WHERE subject_id = ?",
                     (subject_id,)).fetchone()
    conn.close()
    s = dict(r) if r else {'random_count': 0, 'wrong_exam_count': 0}
    s['progress'] = p['last_index'] if p else 0
    return s


def set_setting(subject_id, field, value):
    assert field in ('random_count', 'wrong_exam_count')
    conn = get_conn()
    conn.execute("""
        INSERT INTO subject_settings(subject_id, %s) VALUES (?, ?)
        ON CONFLICT(subject_id) DO UPDATE SET %s = excluded.%s
    """ % (field, field, field), (subject_id, value))
    conn.commit()
    conn.close()


def reset_progress(subject_id):
    conn = get_conn()
    conn.execute("DELETE FROM practice_progress WHERE subject_id = ?", (subject_id,))
    conn.commit()
    conn.close()


def toggle_favorite(qid):
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM favorites WHERE question_id = ?",
                          (qid,)).fetchone()
    if exists:
        conn.execute("DELETE FROM favorites WHERE question_id = ?", (qid,))
        fav = False
    else:
        conn.execute("INSERT INTO favorites(question_id) VALUES (?)", (qid,))
        fav = True
    conn.commit()
    conn.close()
    return fav


def is_favorite(qid):
    conn = get_conn()
    r = conn.execute("SELECT 1 FROM favorites WHERE question_id = ?",
                     (qid,)).fetchone()
    conn.close()
    return bool(r)


def get_favorite_ids():
    conn = get_conn()
    rows = conn.execute("SELECT question_id FROM favorites ORDER BY add_time DESC").fetchall()
    conn.close()
    return [r['question_id'] for r in rows]


# ---------------- 进度 / 记录 / 统计 ----------------
def save_progress(subject_id, index):
    conn = get_conn()
    conn.execute("""
        INSERT INTO practice_progress(subject_id, last_index) VALUES (?, ?)
        ON CONFLICT(subject_id) DO UPDATE SET last_index = excluded.last_index
    """, (subject_id, index))
    conn.commit()
    conn.close()


def get_progress(subject_id):
    conn = get_conn()
    r = conn.execute("SELECT last_index FROM practice_progress WHERE subject_id = ?",
                     (subject_id,)).fetchone()
    conn.close()
    return r['last_index'] if r else 0


def record_answer(qid, correct, source):
    conn = get_conn()
    conn.execute("INSERT INTO answer_records(question_id, is_correct, source) VALUES (?,?,?)",
                 (qid, 1 if correct else 0, source))
    conn.commit()
    conn.close()


def save_exam(subject_id, score, total, correct, passed, duration):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO exam_records(subject_id, score, total, correct, passed, duration)
        VALUES (?,?,?,?,?,?)
    """, (subject_id, score, total, correct, 1 if passed else 0, duration))
    conn.commit()
    conn.close()
    return cur.lastrowid


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    stats = {}
    stats['total_answered'] = c.execute("SELECT COUNT(*) FROM answer_records").fetchone()[0]
    stats['total_wrong'] = c.execute(
        "SELECT COUNT(*) FROM wrong_book").fetchone()[0]
    stats['total_favorite'] = c.execute(
        "SELECT COUNT(*) FROM favorites").fetchone()[0]
    stats['total_questions'] = c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    # 今日答题
    stats['today_answered'] = c.execute(
        "SELECT COUNT(*) FROM answer_records WHERE date(answer_time)=date('now','localtime')").fetchone()[0]
    stats['today_wrong'] = c.execute(
        "SELECT COUNT(*) FROM answer_records WHERE date(answer_time)=date('now','localtime') AND is_correct=0").fetchone()[0]
    # 累计正确率
    total = c.execute("SELECT COUNT(*) FROM answer_records").fetchone()[0]
    right = c.execute("SELECT COUNT(*) FROM answer_records WHERE is_correct=1").fetchone()[0]
    stats['accuracy'] = round(right * 100.0 / total, 1) if total else 0
    # 模拟考试记录
    exams = c.execute("""
        SELECT e.*, s.name AS subject_name FROM exam_records e
        JOIN subjects s ON s.id = e.subject_id
        ORDER BY e.exam_time DESC LIMIT 10
    """).fetchall()
    stats['exams'] = [dict(r) for r in exams]
    # 各科目练习进度
    subs = c.execute("""
        SELECT s.id, s.name, s.question_count,
               IFNULL(p.last_index, 0) AS done,
               (SELECT COUNT(*) FROM answer_records a
                 JOIN questions q ON q.id=a.question_id
                WHERE q.subject_id=s.id AND a.is_correct=1 AND a.source='practice') AS right_cnt,
               (SELECT COUNT(*) FROM answer_records a
                 JOIN questions q ON q.id=a.question_id
                WHERE q.subject_id=s.id AND a.is_correct=0 AND a.source='practice') AS wrong_cnt
        FROM subjects s
        LEFT JOIN practice_progress p ON p.subject_id = s.id
        ORDER BY s.id
    """).fetchall()
    stats['subjects'] = [dict(r) for r in subs]
    conn.close()
    return stats


def clear_wrong_book():
    conn = get_conn()
    conn.execute("DELETE FROM wrong_book")
    conn.commit()
    conn.close()
