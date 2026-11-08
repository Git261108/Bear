# -*- coding: utf-8 -*-
"""Excel 题库导入模块

Excel 模板格式（第一行为表头，列顺序可任意，按列名匹配）：
| 题型 | 题目 | 选项A | 选项B | 选项C | 选项D | 选项E | 选项F | 答案 | 解析 |

说明：
- 一个 Excel 文件 = 一个科目（科目名由调用方指定，默认用文件名）
- 支持 .xlsx（openpyxl）和 .xls（xlrd）两种格式
- 题型：单选 / 多选 / 判断
- 判断题只需填 选项A=对 选项B=错，答案填 A 或 B（也可填 对/错/正确/错误/√/×）
- 多选题答案写在一起，如 ABD
"""
import json
import os
import re

import database as db

ANSWER_MAP = {
    '对': 'A', '正确': 'A', '√': 'A', '是': 'A', 'A': 'A', 'TRUE': 'A',
    '错': 'B', '错误': 'B', '×': 'B', '否': 'B', 'B': 'B', 'FALSE': 'B',
}


def _norm(s):
    """单元格转字符串并去掉首尾空白"""
    if s is None:
        return ''
    s = str(s).strip()
    # xlrd 数字单元格可能是 1.0 这类浮点串
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s


def _read_rows(path):
    """按扩展名读取 Excel，返回二维列表"""
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xls':
        import xlrd
        wb = xlrd.open_workbook(path)
        ws = wb.sheet_by_index(0)
        return [[c.value for c in row] for row in ws.get_rows()]
    else:
        from openpyxl import load_workbook
        wb = load_workbook(path, data_only=True)
        ws = wb.active
        return [list(r) for r in ws.iter_rows(values_only=True)]


def _norm_answer(raw, qtype):
    a = _norm(raw).upper().replace(' ', '').replace('，', ',')
    if qtype == '判断':
        return ANSWER_MAP.get(a, ANSWER_MAP.get(_norm(raw), ''))
    if qtype == '多选':
        letters = sorted(set(re.findall(r'[A-Fa-f]', a)))
        return ''.join(l.upper() for l in letters)
    m = re.search(r'[A-Fa-f]', a)
    return m.group(0).upper() if m else ''


def import_excel(path, subject_name=None):
    """把一个 Excel 文件导入为一个科目，返回 (成功条数, 错误列表)

    subject_name: 科目名，默认取文件名；若科目已存在则先清空其旧题目。
    """
    subject_name = (subject_name or os.path.splitext(os.path.basename(path))[0]).strip()
    rows = _read_rows(path)
    if not rows:
        raise ValueError('Excel 文件为空')

    header = [_norm(h) for h in rows[0]]
    col_map = {}
    aliases = {
        '题型': ['题型', '类型', 'qtype'],
        '题目': ['题目', '问题', 'question'],
        '答案': ['答案', '正确答案', 'answer'],
        '解析': ['解析', '解释', '说明', 'explanation'],
    }
    for i, h in enumerate(header):
        for key, names in aliases.items():
            if h in names:
                col_map[key] = i
        m = re.match(r'选项\s*([A-Fa-f])$', h)
        if m:
            col_map[f'opt{m.group(1).upper()}'] = i
    for key in ['题型', '题目', '答案']:
        if key not in col_map:
            raise ValueError(f'Excel 缺少必需列：{key}，请使用提供的模板')

    def cell(row, i):
        """安全取单元格（列不存在或越界返回空串）"""
        if i is None or i >= len(row):
            return ''
        return _norm(row[i])

    conn = db.get_conn()
    conn.execute("INSERT OR IGNORE INTO subjects(name) VALUES (?)", (subject_name,))
    r = conn.execute("SELECT id FROM subjects WHERE name = ?", (subject_name,)).fetchone()
    sid = r['id']
    conn.execute("DELETE FROM questions WHERE subject_id = ?", (sid,))
    conn.commit()

    errors, success = [], 0
    for line_no, row in enumerate(rows[1:], start=2):
        if not row or not any(row):
            continue
        try:
            qtype = cell(row, col_map['题型'])
            question = cell(row, col_map['题目']).replace('\n', ' ').strip()
            answer_raw = row[col_map['答案']] if col_map['答案'] < len(row) else ''
            explanation = cell(row, col_map.get('解析'))

            if not question:
                raise ValueError('题目为空')
            if qtype not in ('单选', '多选', '判断'):
                raise ValueError(f'题型必须是 单选/多选/判断，当前为"{qtype}"')

            # 组装选项
            if qtype == '判断':
                options = ['对', '错']
            else:
                options = []
                for letter in 'ABCDEF':
                    v = cell(row, col_map.get(f'opt{letter}'))
                    if v:
                        options.append(v)
                if qtype == '单选' and len(options) < 2:
                    raise ValueError('单选题至少需要 2 个选项')
                if qtype == '多选' and len(options) < 3:
                    raise ValueError('多选题至少需要 3 个选项')

            answer = _norm_answer(answer_raw, qtype)
            if not answer:
                raise ValueError(f'答案"{_norm(answer_raw)}"无法识别')
            if qtype == '单选' and len(answer) != 1:
                raise ValueError('单选题答案只能是一个字母')
            if qtype == '多选' and len(answer) < 2:
                raise ValueError('多选题答案至少两个字母')
            if qtype != '判断' and any(ord(a) - 65 >= len(options) for a in answer):
                raise ValueError('答案超出选项范围')

            conn.execute(
                "INSERT INTO questions(subject_id, chapter, qtype, question, options, answer, explanation)"
                " VALUES (?,?,?,?,?,?,?)",
                (sid, '', qtype, question, json.dumps(options, ensure_ascii=False),
                 answer, explanation))
            success += 1
        except Exception as e:
            errors.append(f'第 {line_no} 行：{e}')
    conn.commit()
    conn.close()
    db.refresh_subject_counts()
    return success, errors


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('用法: python import_excel.py 题库文件.xlsx [科目名]')
        print('科目名默认取文件名；同名科目会被清空后重新导入')
        sys.exit(1)
    name = sys.argv[2] if len(sys.argv) > 2 else None
    n, errs = import_excel(sys.argv[1], subject_name=name)
    print(f'导入成功 {n} 题')
    for e in errs[:20]:
        print(e)
