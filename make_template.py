# -*- coding: utf-8 -*-
"""生成 Excel 题库模板（题库模板.xlsx），含少量示例题"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

wb = Workbook()
ws = wb.active
ws.title = '题库'

headers = ['题型', '题目', '选项A', '选项B', '选项C', '选项D', '选项E', '选项F', '答案', '解析']
ws.append(headers)

sample = [
    ['单选', '驾驶机动车在高速公路上行驶，遇有雾、雨、雪等能见度在50米以下时，最高时速不得超过多少？',
     '20公里/小时', '30公里/小时', '40公里/小时', '60公里/小时', '', '', 'A',
     '能见度低于50米时，最高时速不得超过20公里/小时。'],
    ['判断', '驾驶机动车在没有中心线的城市道路上，最高时速不能超过50公里。',
     '对', '错', '', '', '', '', 'B',
     '没有中心线的城市道路最高时速为30公里。'],
    ['多选', '下列哪些行为属于交通违法行为？',
     '酒后驾驶', '超速行驶', '疲劳驾驶', '按信号灯通行', '', '', 'ABC',
     '酒后驾驶、超速行驶、疲劳驾驶均属交通违法行为。'],
    ['判断', '夜间驾驶机动车会车时，应当使用远光灯。',
     '对', '错', '', '', '', '', 'B',
     '会车时距对向来车150米以内应改用近光灯。'],
    ['单选', '行车中遇前方道路突然塌陷，应当如何处置？',
     '紧急制动', '立即停车并设置警示标志', '加速冲过', '倒车离开', '', '', 'B',
     '应立即停车并设置警示标志，防止后车发生事故。'],
]

for row in sample:
    ws.append(row)

# 样式
fill = PatternFill('solid', fgColor='2B7DE9')
for cell in ws[1]:
    cell.font = Font(color='FFFFFF', bold=True)
    cell.fill = fill
    cell.alignment = Alignment(horizontal='center', vertical='center')

widths = [8, 48, 16, 16, 16, 16, 10, 10, 8, 42]
for i, w in enumerate(widths, 1):
    ws.column_dimensions[chr(64 + i)].width = w

wb.save('题库模板.xlsx')
print('已生成 题库模板.xlsx')
