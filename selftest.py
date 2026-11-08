# -*- coding: utf-8 -*-
"""端到端自测脚本"""
import app as appmod

c = appmod.app.test_client()

def check(name, ok, extra=''):
    print(('PASS' if ok else 'FAIL'), name, extra)

# 页面渲染
for url in ['/', '/subject/1', '/practice/1?mode=order', '/wrongbook/1', '/profile',
            '/manage', '/import']:
    r = c.get(url)
    check(f'GET {url}', r.status_code == 200, r.status_code)

# 顺序练习题目
r = c.get('/api/questions/1?mode=order')
qs = r.get_json()['questions']
check('api questions order', r.status_code == 200 and len(qs) == 5 and 'answer' not in qs[0], len(qs))

# 随机练习：档位题数即时生效，不持久化
r = c.get('/api/questions/1?mode=random&count=3')
check('api random count=3', len(r.get_json()['questions']) == 3)
r = c.get('/api/settings/1')
check('random_count not persisted', r.get_json()['random_count'] == 0, r.get_json()['random_count'])
# 档位超过题库数 → 直接按全部题库数量
r = c.get('/api/questions/1?mode=random&count=999')
check('api random count>total -> all', len(r.get_json()['questions']) == 5)
# 仅单选（模板中有 2 道单选）
r = c.get('/api/questions/1?mode=random&count=100&qtype=单选')
check('api qtype filter 单选', all(q['qtype'] == '单选' for q in r.get_json()['questions']) and len(r.get_json()['questions']) == 2,
      len(r.get_json()['questions']))
# 综合模式排序：判断→单选→多选（模板录入顺序为 单,判,多,判,单）
r = c.get('/api/questions/1?mode=random&count=100')
types = [q['qtype'] for q in r.get_json()['questions']]
check('api combined order 判→单→多', types == ['判断', '判断', '单选', '单选', '多选'], types)

# 答题：答对第一题（答案 A）
qid1 = qs[0]['id']
r = c.post('/api/answer', json={'question_id': qid1, 'picked': ['A']})
d = r.get_json()
check('api answer correct', d['correct'] is True, d['answer'])

# 答错第二题（判断题，答案 B）
qid2 = qs[1]['id']
r = c.post('/api/answer', json={'question_id': qid2, 'picked': ['A']})
d = r.get_json()
check('api answer wrong -> judge', d['correct'] is False, d['answer'])

# 错题本（按科目）
r = c.get('/api/questions/1?mode=wrong')
wqs = r.get_json()['questions']
check('api wrong exam random', len(wqs) == 1, len(wqs))

# 错题本考试：档位题数即时生效，不持久化
r = c.get('/api/questions/1?mode=wrong&count=1')
check('api wrong count=1', len(r.get_json()['questions']) == 1)
r = c.get('/api/settings/1')
check('wrong_exam_count not persisted', r.get_json()['wrong_exam_count'] == 0, r.get_json()['wrong_exam_count'])

# 错题本学习列表（带答案）
r = c.get('/api/wrong/list/1')
wl = r.get_json()['questions']
check('wrong learn list with answer', len(wl) == 1 and 'answer' in wl[0], wl[0].get('answer') if wl else '')

# 手动移出错题本
r = c.post(f'/api/wrong/remove/{qid2}')
r = c.get('/api/wrong/list/1')
check('wrong manual remove', len(r.get_json()['questions']) == 0)

# 收藏
r = c.post(f'/api/favorite/{qid1}')
check('api favorite on', r.get_json()['favorite'] is True)

# 进度保存 / 顺序练习从进度继续 / 重置
c.post('/api/progress/1', json={'index': 3})
r = c.get('/api/settings/1')
check('progress saved', r.get_json()['progress'] == 3)
# 已答 3 题 → 再次进入从第 4 题开始（start=3，即录入顺序的第 4 题）
r = c.get('/api/questions/1?mode=order')
d = r.get_json()
check('order resume at 4th', d['start'] == 3 and d['questions'][0]['id'] == qs[3]['id'],
      f"start={d['start']}")
# 全部答完（进度=总题数）→ 再次进入直接是最后一题
c.post('/api/progress/1', json={'index': 5})
r = c.get('/api/questions/1?mode=order')
d = r.get_json()
check('order all-done -> last', d['start'] == 4 and len(d['questions']) == 1,
      f"start={d['start']}")
r = c.post('/api/progress/1/reset')
r = c.get('/api/questions/1?mode=order')
d = r.get_json()
check('order reset -> first', d['start'] == 0 and d['questions'][0]['id'] == qs[0]['id'])
# 顺序练习按录入顺序（ORDER BY id）
check('order insertion sequence',
      [q['id'] for q in d['questions']] == [q['id'] for q in qs])

# 模拟考试
r = c.get('/api/exam/start/1')
d = r.get_json()
check('api exam start', r.status_code == 200 and d['minutes'] == 45, d.get('minutes'))
answers = {str(q['id']): ['A'] for q in d['questions']}
r = c.post('/api/exam/submit', json={'subject_id': 1, 'duration': 300, 'answers': answers})
d = r.get_json()
check('api exam submit', r.status_code == 200 and 'score' in d, f"score={d.get('score')} passed={d.get('passed')}")

# 统计
r = c.get('/api/stats')
s = r.get_json()
check('api stats', s['total_answered'] > 0, s['total_answered'])

# ================= 自定义科目 =================
r = c.get('/api/subjects')
subs = r.get_json()['subjects']
check('api subjects list', r.status_code == 200 and len(subs) >= 1, len(subs))

# 上传 Excel 创建新科目（无科目/章节列的新模板）
with open('题库模板.xlsx', 'rb') as fp:
    r = c.post('/api/subjects/upload', data={
        'file': (fp, '法考民法.xlsx'), 'name': '测试科目X'}, content_type='multipart/form-data')
d = r.get_json()
check('api subject upload', r.status_code == 200 and d.get('count') == 5, d.get('message'))
sid_new = d.get('subject_id')

# 同名创建应被拒绝
with open('题库模板.xlsx', 'rb') as fp:
    r = c.post('/api/subjects/upload', data={
        'file': (fp, 'x.xlsx'), 'name': '测试科目X'}, content_type='multipart/form-data')
check('api duplicate subject rejected', r.status_code == 400, r.get_json().get('error'))

# 重命名
r = c.post('/api/subjects/%d/rename' % sid_new, json={'name': '测试科目Y'})
check('api subject rename', r.status_code == 200)
r = c.get('/api/subjects')
check('renamed visible', any(s['name'] == '测试科目Y' for s in r.get_json()['subjects']))

# 重命名为已存在的名称应被拒绝
r = c.post('/api/subjects/%d/rename' % sid_new, json={'name': '科目一'})
check('rename duplicate rejected', r.status_code == 400)

# 缺少名称的本地导入请求应被拒绝
r = c.post('/api/import/local', json={})
check('import local needs name', r.status_code == 400)

# 删除科目后错题一并删除
c.post('/api/answer', json={'question_id': qs[2]['id'], 'picked': ['A', 'B']})  # 制造错题(多选, 答案ABC)
r = c.post('/api/subjects/%d/delete' % sid_new)
check('api subject delete', r.status_code == 200)
r = c.get('/api/subjects')
check('deleted gone', not any(s['name'] == '测试科目Y' for s in r.get_json()['subjects']))
