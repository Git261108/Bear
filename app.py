# -*- coding: utf-8 -*-
"""驾考宝典背题应用 - Flask 主程序
运行: python app.py  然后浏览器打开 http://127.0.0.1:5000
手机访问: 与电脑同一局域网，打开 http://电脑IP:5000
"""
import os
from flask import Flask, render_template, request, jsonify

import database as db
import filepicker
from import_excel import import_excel

app = Flask(__name__)

# 模拟考试配置（科目一 100 题 45 分钟；科目四 50 题 30 分钟）
EXAM_RULES = {
    '科目一': {'count': 100, 'minutes': 45, 'pass_score': 90, 'per_score': 1},
    '科目二': {'count': 100, 'minutes': 45, 'pass_score': 90, 'per_score': 1},
    '科目三': {'count': 50, 'minutes': 30, 'pass_score': 90, 'per_score': 2},
    '科目四': {'count': 50, 'minutes': 30, 'pass_score': 90, 'per_score': 2},
}
DEFAULT_RULE = {'count': 100, 'minutes': 45, 'pass_score': 90, 'per_score': 1}


def exam_rule(subject_name):
    for key, rule in EXAM_RULES.items():
        if key in subject_name:
            return rule
    return DEFAULT_RULE


def check_answer(q, picked):
    """picked: 选项字母列表，如 ['A','D']"""
    correct = set(q['answer'])
    return set(picked) == correct


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/subject/<int:subject_id>')
def subject_page(subject_id):
    sub = next((s for s in db.list_subjects() if s['id'] == subject_id), None)
    if not sub:
        return render_template('index.html'), 302
    return render_template('subject.html', subject=sub,
                           settings=db.get_settings(subject_id))


@app.route('/practice/<int:subject_id>')
def practice(subject_id):
    mode = request.args.get('mode', 'order')   # order 顺序 / random 随机 / wrong 错题考试 / favorite 收藏
    return render_template('practice.html', subject_id=subject_id, mode=mode)


@app.route('/wrongbook/<int:subject_id>')
def wrongbook(subject_id):
    """错题本学习模式：直接显示答案"""
    return render_template('wrongbook.html', subject_id=subject_id)


@app.route('/exam/<int:subject_id>')
def exam_page(subject_id):
    return render_template('exam.html', subject_id=subject_id)


@app.route('/profile')
def profile():
    return render_template('profile.html')


@app.route('/manage')
def manage():
    """科目库管理页"""
    return render_template('manage.html')


@app.route('/import')
def import_page():
    """导入新科目页"""
    return render_template('import.html')


# ---------------- API ----------------
TYPE_ORDER = {'判断': 0, '单选': 1, '多选': 2}   # 综合模式排序：判断→单选→多选


def _filter_sort(qs, qtype):
    """按题型过滤；综合模式下按 判断→单选→多选 排序"""
    if qtype in TYPE_ORDER:
        return [q for q in qs if q['qtype'] == qtype]
    return sorted(qs, key=lambda q: TYPE_ORDER.get(q['qtype'], 3))


@app.route('/api/questions/<int:subject_id>')
def api_questions(subject_id):
    mode = request.args.get('mode', 'order')
    qtype = request.args.get('qtype', '')   # 单选/多选/判断，空=综合
    try:
        count = int(request.args.get('count', 0))
    except (ValueError, TypeError):
        count = 0
    if count < 0:
        count = 0

    start = 0   # 顺序练习模式的起始偏移
    if mode == 'wrong':
        # 错题本考试：随机 + 档位题数（档位超过错题数时自然取全部）
        ids = db.get_wrong_ids(subject_id)
        qs = db.get_questions(subject_id, ids, shuffle=True) if ids else []
        qs = _filter_sort(qs, qtype)
        if count > 0:
            qs = qs[:count]
    elif mode == 'favorite':
        ids = db.get_favorite_ids()
        qs = db.get_questions(subject_id, ids) if ids else []
    elif mode == 'random':
        # 随机练习：随机抽题 + 档位题数（档位超过题库数时自然取全部）
        qs = db.get_questions(subject_id, shuffle=True)
        qs = _filter_sort(qs, qtype)
        if count > 0:
            qs = qs[:count]
    else:
        # 顺序练习：按录入顺序，从上次进度继续；全部答完后再次进入 → 最后一题
        qs = db.get_questions(subject_id)   # ORDER BY id，即录入顺序
        total = len(qs)
        progress = min(max(db.get_progress(subject_id), 0), total)
        start = progress if progress < total else total - 1
        qs = qs[start:]
    # 不把答案直接下发给前端，判卷在服务端
    for q in qs:
        q.pop('answer', None)
    return jsonify({'questions': qs, 'start': start})


@app.route('/api/wrong/list/<int:subject_id>')
def api_wrong_list(subject_id):
    """错题本学习模式：带答案、解析，按题目录入顺序"""
    ids = db.get_wrong_ids(subject_id)
    qs = db.get_questions(subject_id, ids) if ids else []
    return jsonify({'questions': qs})


@app.route('/api/wrong/remove/<int:qid>', methods=['POST'])
def api_wrong_remove(qid):
    """从错题本移除（学习/考试模式下手动移除）"""
    db.remove_wrong(qid)
    return jsonify({'ok': True})


@app.route('/api/settings/<int:subject_id>')
def api_settings(subject_id):
    return jsonify(db.get_settings(subject_id))


@app.route('/api/progress/<int:subject_id>/reset', methods=['POST'])
def api_progress_reset(subject_id):
    db.reset_progress(subject_id)
    return jsonify({'ok': True})


@app.route('/api/question/<int:qid>')
def api_question(qid):
    q = db.get_question(qid)
    if not q:
        return jsonify({'error': '题目不存在'}), 404
    q.pop('answer', None)
    q['favorite'] = db.is_favorite(qid)
    return jsonify(q)


@app.route('/api/answer', methods=['POST'])
def api_answer():
    data = request.get_json()
    qid, picked = data.get('question_id'), data.get('picked', [])
    source = data.get('source', 'practice')
    q = db.get_question(qid)
    if not q:
        return jsonify({'error': '题目不存在'}), 404
    correct = check_answer(q, picked)
    db.record_answer(qid, correct, source)
    if correct:
        db.remove_wrong(qid)          # 做对后自动移出错题本
    else:
        db.add_wrong(qid)
    return jsonify({'correct': correct, 'answer': q['answer'],
                    'explanation': q['explanation']})


@app.route('/api/progress/<int:subject_id>', methods=['POST'])
def api_progress(subject_id):
    db.save_progress(subject_id, int(request.get_json().get('index', 1)))
    return jsonify({'ok': True})


@app.route('/api/progress/<int:subject_id>')
def api_get_progress(subject_id):
    return jsonify({'index': db.get_progress(subject_id)})


@app.route('/api/favorite/<int:qid>', methods=['POST'])
def api_favorite(qid):
    return jsonify({'favorite': db.toggle_favorite(qid)})


@app.route('/api/wrong/clear', methods=['POST'])
def api_clear_wrong():
    db.clear_wrong_book()
    return jsonify({'ok': True})


@app.route('/api/exam/start/<int:subject_id>')
def api_exam_start(subject_id):
    rule = DEFAULT_RULE
    subjects = {s['id']: s for s in db.list_subjects()}
    if subject_id in subjects:
        rule = exam_rule(subjects[subject_id]['name'])
    qs = db.get_questions(subject_id, shuffle=True)[:rule['count']]
    for q in qs:
        q.pop('answer', None)
    return jsonify({'questions': qs, 'minutes': rule['minutes'],
                    'pass_score': rule['pass_score'], 'per_score': rule['per_score']})


@app.route('/api/exam/submit', methods=['POST'])
def api_exam_submit():
    data = request.get_json()
    subject_id = data['subject_id']
    answers = data.get('answers', {})          # {qid: [picked]}
    duration = int(data.get('duration', 0))
    subjects = {s['id']: s for s in db.list_subjects()}
    rule = exam_rule(subjects[subject_id]['name']) if subject_id in subjects else DEFAULT_RULE

    qs = db.get_questions(subject_id)
    qmap = {q['id']: q for q in qs}
    total, correct = len(answers), 0
    detail = []
    for qid_str, picked in answers.items():
        qid = int(qid_str)
        q = qmap.get(qid)
        if not q:
            continue
        ok = check_answer(q, picked)
        correct += ok
        db.record_answer(qid, ok, 'exam')
        if not ok:
            db.add_wrong(qid)
        else:
            db.remove_wrong(qid)
        detail.append({'id': qid, 'correct': ok, 'answer': q['answer'],
                       'picked': picked})
    score = int(correct * rule['per_score'])
    passed = score >= rule['pass_score']
    db.save_exam(subject_id, score, total, correct, passed, duration)
    return jsonify({'score': score, 'total': total, 'correct': correct,
                    'passed': passed, 'pass_score': rule['pass_score'],
                    'duration': duration})


@app.route('/api/stats')
def api_stats():
    return jsonify(db.get_stats())


def _check_excel(filename):
    """校验上传文件扩展名，合法返回 True"""
    return filename and filename.lower().endswith(('.xlsx', '.xls', '.xlsm'))


@app.route('/api/import/local', methods=['POST'])
def api_import_local():
    """选择一个 Excel 文件创建为新科目（安卓打开系统文件选择器，PC 弹文件对话框）

    流程：POST 打开选择器 → 前端轮询 GET /api/import/local/poll 获取结果
    """
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': '请先填写新科目的名称'}), 400
    if db.find_subject_id(name):
        return jsonify({'error': f'科目"{name}"已存在，请换个名称或直接使用它'}), 400
    filepicker.open_excel_dialog(name)
    return jsonify({'pending': True})


@app.route('/api/import/local/poll')
def api_import_poll():
    """轮询文件选择结果；选中后自动导入为新科目"""
    r = filepicker.poll_result()
    state = r.get('state')
    if state == 'done':
        filepicker.reset()
        path, name = r['path'], filepicker.pending_name()
        if not _check_excel(path):
            return jsonify({'state': 'error', 'error': '请选择 .xlsx 或 .xls 格式的 Excel 文件'})
        if db.find_subject_id(name):
            return jsonify({'state': 'error', 'error': f'科目"{name}"已存在，请换个名称'})
        try:
            n, errors = import_excel(path, subject_name=name)
            msg = f'科目"{name}"创建成功，导入 {n} 题'
            if errors:
                msg += f'，失败 {len(errors)} 条：' + '；'.join(errors[:5])
            sid = db.find_subject_id(name)
            return jsonify({'state': 'done', 'message': msg,
                            'subject_id': sid, 'count': n})
        except Exception as e:
            return jsonify({'state': 'error', 'error': f'导入失败：{e}'})
    if state in ('cancelled', 'error', 'idle'):
        return jsonify({'state': state, 'error': r.get('error', '已取消选择')})
    return jsonify({'state': state})   # waiting，继续轮询


# ---------------- 科目管理 ----------------
@app.route('/api/subjects')
def api_subjects():
    return jsonify({'subjects': db.list_subjects()})


@app.route('/api/subjects/<int:sid>/rename', methods=['POST'])
def api_subject_rename(sid):
    name = (request.get_json() or {}).get('name', '').strip()
    if not name:
        return jsonify({'error': '科目名称不能为空'}), 400
    exist = db.find_subject_id(name)
    if exist and exist != sid:
        return jsonify({'error': f'科目"{name}"已存在'}), 400
    db.rename_subject(sid, name)
    return jsonify({'ok': True})


@app.route('/api/subjects/<int:sid>/delete', methods=['POST'])
def api_subject_delete(sid):
    db.delete_subject(sid)   # 级联删除该科目的题目、错题、收藏、进度、成绩
    return jsonify({'ok': True})


@app.route('/api/subjects/upload', methods=['POST'])
def api_subject_upload():
    """上传一个 Excel 创建为新科目（PC 网页上传；安卓也可以用 /api/import/local）"""
    f = request.files.get('file')
    if not f or not _check_excel(f.filename):
        return jsonify({'error': '请选择 .xlsx 或 .xls 格式的 Excel 文件'}), 400
    filename = f.filename or ''
    name = (request.form.get('name') or '').strip() \
        or os.path.splitext(filename)[0].strip()
    if not name:
        return jsonify({'error': '请填写科目名称'}), 400
    if db.find_subject_id(name):
        return jsonify({'error': f'科目"{name}"已存在，请换个名称'}), 400
    path = os.path.join(db.DATA_DIR, 'upload' + os.path.splitext(filename)[1].lower())
    f.save(path)
    try:
        n, errors = import_excel(path, subject_name=name)
        msg = f'科目"{name}"创建成功，导入 {n} 题'
        if errors:
            msg += f'，失败 {len(errors)} 条：' + '；'.join(errors[:5])
        return jsonify({'ok': True, 'message': msg,
                        'subject_id': db.find_subject_id(name), 'count': n})
    except Exception as e:
        db.delete_subject(db.find_subject_id(name) or 0)   # 导入失败不留下空科目
        return jsonify({'error': f'导入失败：{e}'}), 400


if __name__ == '__main__':
    db.init_db()
    # 局域网可访问，手机通过 http://电脑IP:5000 打开
    app.run(host='0.0.0.0', port=5000, debug=False)
