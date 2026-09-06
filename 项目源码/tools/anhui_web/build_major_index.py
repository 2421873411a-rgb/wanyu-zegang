# -*- coding: utf-8 -*-
"""T1 专业智能匹配引擎 · 数据侧：构建专业倒排索引 major-index.json（v2）。

匹配口径（推导亮明依据，绝不臆测）：
- zy 原文按分隔符切分（、，,；;／/＋+ 空格），剥「本科：/研究生：/大专：」前缀与专业代码
- token 命中目录成员 → explicit（该专业的考生明确可报）
- token 为目录「XX类」 → by_class（该类全部成员专业的考生可报，依据=该岗要求『XX类』）
- token 为「XX门类」 → by_class 展开到该门类下全部类（依据=该岗要求『XX门类』）
- token 为自定义类名（财会审计类等） → 别名映射到标准类后按 by_class 处理
- token 为 4 位学科代码（0301 等，独立或与专业名连写） → 代码映射到类后按 by_class 处理
- token 含「不限」 → unlimited
- 其余 → unclassified_tokens（宁缺勿错，绝不强行归类）
匹配依据原文由前端从 jobs_lite.zy 现取（索引不冗余存原文）。

v2 变更（2026-09-06，覆盖缺口 95.5%→99%+）：
1. 门类名展开（经济学门类/法学门类/工学门类…→ 门类下全部类）
2. 自定义类名别名词典（财会审计类→工商管理类+会计+审计…）
3. 4 位学科代码映射（0301→法学类+法学…，独立 token 与连写前缀两种形态）
4. 解析噪音词表（一级学科/二级学科/不含特设/专业学位…不再误报 unclassified）
5. 「XX学类/XX类」回退：剥尾部「类」后重查目录（应用经济学类→应用经济学）
6. 「方向」后缀剥离（财务管理方向→财务管理）
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[2] / "网站"
SPLIT_RE = re.compile(r"[、，,；;／/＋+\s（）()：:．·\-—。]+")
CODE_RE = re.compile(r"^\d{5,6}[A-Za-z]?")
CODE4_PREFIX_RE = re.compile(r"^\d{4}(?=[\u4e00-\u9fff])")
CODE4_STANDALONE_RE = re.compile(r"^\d{4}$")
ENUM_PREFIX_RE = re.compile(r"^\d+[.、]")
UNLIM_RE = re.compile(r"(不限|无专业限制|专业不限|不受专业限制)")
TAIL_RE = re.compile(r"(等专业|相关专业|专业|类别|方向|等)+$")
MASTERS_TAIL_RE = re.compile(r"(专业硕士学位|专业硕士|专业学位硕士|专业学位)$")

# —— 解析噪音：纯限定语/层级标记，真实专业名在同 zy 的其他 token 里 ——
STOPWORDS = {
    "一级学科", "二级学科", "不含特设", "专业学位", "专业硕士", "专业型硕士",
    "专业硕士学位", "学科门类", "门类", "一级", "二级", "专科", "本科", "研究生",
    "硕士", "博士", "学士", "含", "不含", "等", "K", "。", "学", "类", "方向",
    "及以上", "或",
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12", "13",
    "14", "本科专业须与本岗位要求一致", "研究生专业须与本岗位要求一致",
    "专业技术", "管理岗位", "专业代码", "类别代码", "专硕", "大学",
}

# —— 4 位研究生学科代码 → 类（研究生一级学科名/本科类名，构建时按目录存在性过滤）——
CODE4_TO_CLASSES: dict[str, list[str]] = {
    "0201": ["理论经济学"], "0202": ["应用经济学"],
    "0251": ["应用统计"], "0252": ["税务"], "0253": ["国际商务"], "0254": ["保险"],
    "0255": ["资产评估"], "0257": ["审计"],
    "0301": ["法学"], "0302": ["政治学"], "0303": ["社会学"], "0304": ["民族学"],
    "0305": ["马克思主义理论"], "0306": ["公安学"], "0307": ["中共党史党建学"],
    "0351": ["法律"], "0352": ["社会工作"], "0353": ["警务"], "0354": ["知识产权"],
    "0401": ["教育学"], "0402": ["心理学"], "0403": ["体育学"],
    "0451": ["教育"], "0452": ["体育"], "0453": ["国际中文教育"], "0454": ["应用心理"],
    "0501": ["中国语言文学"], "0502": ["外国语言文学"], "0503": ["新闻传播学"],
    "0551": ["翻译"], "0552": ["新闻与传播"], "0553": ["出版"],
    "0554": ["国际中文教育"],
    "0601": ["考古学"], "0602": ["中国史"], "0603": ["世界史"],
    "0701": ["数学"], "0702": ["物理学"], "0703": ["化学"], "0704": ["天文学"],
    "0705": ["地理学"], "0706": ["大气科学"], "0707": ["海洋科学"],
    "0708": ["地球物理学"], "0709": ["地质学"], "0710": ["生物学"],
    "0711": ["系统科学"], "0712": ["科学技术史"], "0713": ["生态学"], "0714": ["统计学"],
    "0770": ["心理学"], "0771": ["心理学"], "0772": ["力学"], "0773": ["材料科学与工程"],
    "0774": ["电子科学与技术"], "0775": ["计算机科学与技术"], "0776": ["环境科学与工程"],
    "0777": ["生物医学工程"], "0778": ["基础医学"], "0779": ["公共卫生与预防医学"],
    "0780": ["药学"], "0781": ["中药学"],
    "0801": ["力学"], "0802": ["机械工程"], "0803": ["光学工程"],
    "0804": ["仪器科学与技术"], "0805": ["材料科学与工程"], "0806": ["冶金工程"],
    "0807": ["动力工程及工程热物理"], "0808": ["电气工程"], "0809": ["电子科学与技术"],
    "0810": ["信息与通信工程"], "0811": ["控制科学与工程"], "0812": ["计算机科学与技术"],
    "0813": ["建筑学"], "0814": ["土木工程"], "0815": ["水利工程"],
    "0816": ["测绘科学与技术"], "0817": ["化学工程与技术"], "0818": ["地质资源与地质工程"],
    "0819": ["矿业工程"], "0820": ["石油与天然气工程"], "0821": ["纺织科学与工程"],
    "0822": ["轻工技术与工程"], "0823": ["交通运输工程"], "0824": ["船舶与海洋工程"],
    "0825": ["航空宇航科学与技术"], "0826": ["兵器科学与技术"], "0827": ["核科学与技术"],
    "0828": ["农业工程"], "0829": ["林业工程"], "0830": ["环境科学与工程"],
    "0831": ["生物医学工程"], "0832": ["食品科学与工程"], "0833": ["城乡规划学"],
    "0834": ["风景园林学"], "0835": ["软件工程"], "0836": ["生物工程"],
    "0837": ["安全科学与工程"], "0838": ["公安技术"], "0839": ["网络空间安全"],
    "0840": ["集成电路科学与工程"],
    "0851": ["建筑"], "0853": ["城市规划"], "0854": ["电子信息"], "0855": ["机械"],
    "0856": ["材料与化工"], "0857": ["资源与环境"], "0858": ["能源动力"],
    "0859": ["土木水利"],
    "0860": ["生物与医药"], "0861": ["交通运输"],
    "0901": ["作物学"], "0902": ["园艺学"], "0903": ["农业资源与环境"],
    "0904": ["植物保护"], "0905": ["畜牧学"], "0906": ["兽医学"],
    "0907": ["林学"], "0908": ["水产"], "0909": ["草学"],
    "0951": ["农业"], "0952": ["农业"], "0953": ["风景园林"], "0954": ["林业"],
    "0955": ["畜牧"], "0956": ["渔业"], "0957": ["兽医"],
    "1001": ["基础医学"], "1002": ["临床医学"], "1003": ["口腔医学"],
    "1004": ["公共卫生与预防医学"], "1005": ["中医"], "1006": ["中西医结合"],
    "1007": ["药学"], "1008": ["中药"], "1009": ["特种医学"],
    "1010": ["医学技术"], "1011": ["护理"],
    "1051": ["临床医学"], "1052": ["口腔医学"], "1053": ["公共卫生"],
    "1054": ["护理"], "1055": ["药学"], "1056": ["中药"], "1057": ["中医"],
    "1201": ["管理科学与工程"], "1202": ["工商管理"], "1203": ["农林经济管理"],
    "1204": ["公共管理"], "1205": ["图书情报与档案管理"],
    "1251": ["工商管理"], "1252": ["公共管理"], "1253": ["会计"],
    "1254": ["旅游管理"], "1255": ["图书情报"], "1256": ["工程管理"], "1257": ["审计"],
    "1301": ["艺术学理论"], "1302": ["音乐与舞蹈学"], "1303": ["戏剧与影视学"],
    "1304": ["美术学"], "1305": ["设计学"],
    "1351": ["艺术"], "1352": ["音乐"], "1353": ["舞蹈"], "1354": ["戏剧与影视"],
    "1355": ["戏曲与曲艺"], "1356": ["美术与书法"], "1357": ["设计"],
    "1401": ["集成电路科学与工程"], "1402": ["国家安全学"], "1403": ["设计学"],
    "1404": ["遥感科学与技术"], "1405": ["智能科学与技术"], "1406": ["区域国别学"],
    "1451": ["中共党史党建学"], "1452": ["纪检监察学"],
    # 专科（高职）专业类代码：63 财经商贸大类
    "6301": ["财政税务类"], "6302": ["金融类"], "6303": ["财务会计类"],
    "6304": ["统计类"], "6305": ["经济贸易类"], "6306": ["工商企业管理类"],
    "6307": ["市场营销类"], "6308": ["电子商务类"], "6309": ["物流类"],
}

# —— 十二学科门类 → 门类下类（本科类名 + 研究生一级学科名 + 专硕领域，按目录过滤）——
MENLEI_TO_CLASSES: dict[str, list[str]] = {
    "哲学门类": ["哲学", "哲学类"],
    "经济学门类": ["理论经济学", "应用经济学", "经济学类", "财政学类", "金融学类",
                 "经济与贸易类", "金融", "税务", "国际商务", "保险", "资产评估",
                 "应用统计", "财政学", "经济学", "经济统计学", "国际贸易学"],
    "法学门类": ["法学", "政治学", "社会学", "民族学", "马克思主义理论", "公安学",
               "法学类", "政治学类", "社会学类", "民族学类", "马克思主义理论类",
               "公安学类", "法律", "社会工作", "警务", "监狱学", "知识产权",
               "国际政治", "外交学", "政治学、经济学与哲学"],
    "教育学门类": ["教育学", "教育", "体育学", "体育", "教育学类", "体育学类",
                "教育类", "体育类", "教育管理", "学科教学", "心理健康教育",
                "学前教育", "小学教育", "特殊教育", "教育技术学", "汉语国际教育",
                "应用心理", "心理学"],
    "文学门类": ["中国语言文学", "外国语言文学", "新闻传播学", "中国语言文学类",
               "外国语言文学类", "新闻传播学类", "翻译", "新闻与传播", "出版",
               "国际中文教育", "汉语国际教育", "英语语言文学", "日语语言文学"],
    "历史学门类": ["考古学", "中国史", "世界史", "历史学类", "文物与博物馆",
                "文物", "博物馆"],
    "理学门类": ["数学", "物理学", "化学", "天文学", "地理学", "大气科学",
               "海洋科学", "地球物理学", "地质学", "生物学", "心理学", "统计学",
               "生态学", "系统科学", "科学技术史", "数学类", "物理学类", "化学类",
               "天文学类", "地理科学类", "大气科学类", "海洋科学类", "地球物理学类",
               "地质学类", "生物科学类", "心理学类", "统计学类"],
    "工学门类": ["力学", "机械工程", "光学工程", "仪器科学与技术", "材料科学与工程",
               "冶金工程", "动力工程及工程热物理", "电气工程", "电子科学与技术",
               "信息与通信工程", "控制科学与工程", "计算机科学与技术", "建筑学",
               "土木工程", "水利工程", "测绘科学与技术", "化学工程与技术",
               "地质资源与地质工程", "矿业工程", "石油与天然气工程", "纺织科学与工程",
               "轻工技术与工程", "交通运输工程", "船舶与海洋工程", "航空宇航科学与技术",
               "兵器科学与技术", "核科学与技术", "农业工程", "林业工程",
               "环境科学与工程", "生物医学工程", "食品科学与工程", "城乡规划学",
               "风景园林学", "软件工程", "生物工程", "安全科学与工程", "公安技术",
               "网络空间安全", "集成电路科学与工程", "力学类", "机械类", "仪器类",
               "材料类", "能源动力类", "电气类", "电子信息类", "自动化类", "计算机类",
               "土木类", "水利类", "测绘类", "化工与制药类", "地质类", "矿业类",
               "纺织类", "轻工类", "交通运输类", "海洋工程类", "航空航天类", "兵器类",
               "核工程类", "农业工程类", "林业工程类", "环境科学与工程类",
               "生物医学工程类", "食品科学与工程类", "建筑类", "安全科学与工程类",
               "生物工程类", "公安技术类", "建筑", "城市规划", "电子信息", "机械",
               "材料与化工", "资源与环境", "能源动力", "土木水利", "生物与医药",
               "交通运输"],
    "农学门类": ["作物学", "园艺学", "农业资源与环境", "植物保护", "畜牧学",
               "兽医学", "林学", "水产", "草学", "植物生产类", "自然保护与环境生态类",
               "动物生产类", "动物医学类", "林学类", "水产类", "草学类",
               "农业", "林业", "兽医", "风景园林"],
    "医学门类": ["基础医学", "临床医学", "口腔医学", "公共卫生与预防医学", "中医",
               "中西医结合", "药学", "中药", "特种医学", "医学技术", "护理",
               "基础医学类", "临床医学类", "口腔医学类", "公共卫生与预防医学类",
               "中医学类", "中医药类", "药学类", "中药学类", "法医学类", "医学技术类",
               "护理学类", "公共卫生", "中医学", "中药学", "护理学"],
    "管理学门类": ["管理科学与工程", "工商管理", "农林经济管理", "公共管理",
                "图书情报与档案管理", "管理科学与工程类", "工商管理类",
                "农业经济管理类", "公共管理类", "图书情报与档案管理类",
                "物流管理与工程类", "工业工程类", "电子商务类", "旅游管理类",
                "会计", "审计", "旅游管理", "图书情报", "工程管理", "工商管理类"],
    "艺术学门类": ["艺术学理论", "音乐与舞蹈学", "戏剧与影视学", "美术学", "设计学",
                "艺术", "音乐", "舞蹈", "戏剧与影视", "戏曲与曲艺", "美术与书法",
                "设计", "艺术学理论类", "音乐与舞蹈学类", "戏剧与影视学类",
                "美术学类", "设计学类"],
}

# —— 自定义类名/常见简称 → 标准类（岗位 zy 原文中的非标准类名）——
ALIAS_TO_CLASSES: dict[str, list[str]] = {
    "财会审计类": ["工商管理类", "会计", "审计", "会计学", "财务管理", "审计学"],
    "会计类": ["工商管理类", "会计", "会计学"],
    "审计类": ["工商管理类", "审计", "审计学"],
    "会计专业硕士": ["会计"],
    "经济金融类": ["理论经济学", "应用经济学", "经济学类", "金融学类", "财政学类",
                 "经济与贸易类", "金融"],
    "应用经济学类": ["应用经济学", "经济学类", "财政学类", "金融学类", "经济与贸易类"],
    "经济贸易类": ["应用经济学", "国际商务", "经济与贸易类", "国际贸易学"],
    "经济学类": ["经济学类", "经济学", "经济统计学", "国民经济管理"],
    "计算机科学与技术类": ["计算机科学与技术", "计算机类", "软件工程"],
    "计算机类": ["计算机类", "计算机科学与技术", "软件工程", "网络工程", "信息安全",
               "物联网工程", "数据科学与大数据技术", "网络空间安全", "智能科学与技术"],
    "软件工程类": ["软件工程", "计算机类"],
    "大数据技术与工程": ["计算机科学与技术", "计算机类"],
    "网络与信息安全": ["网络空间安全", "计算机类"],
    "电子信息类": ["电子信息类", "电子信息工程", "通信工程", "微电子科学与工程",
                 "光电信息科学与工程", "信息工程"],
    "信息与通信工程类": ["信息与通信工程", "电子信息类"],
    "电子科学与技术类": ["电子科学与技术", "电子信息类"],
    "控制科学与工程类": ["控制科学与工程", "自动化类"],
    "电气工程类": ["电气工程", "电气类"],
    "机械工程类": ["机械工程", "机械类"],
    "土木工程类": ["土木工程", "土木类", "土木水利"],
    "土木": ["土木类", "土木工程"],
    "建筑学类": ["建筑学", "建筑类", "建筑"],
    "城乡规划学类": ["城乡规划学", "城乡规划", "建筑类", "城市规划"],
    "城市规划与设计": ["城乡规划学", "城乡规划", "城市规划", "建筑类"],
    "水利工程类": ["水利工程", "水利类", "土木水利"],
    "水利与交通工程": ["水利工程", "交通运输工程", "水利类", "交通运输类"],
    "交通运输工程类": ["交通运输工程", "交通运输类", "交通运输"],
    "测绘科学与技术类": ["测绘科学与技术", "测绘类"],
    "环境科学与工程类": ["环境科学与工程", "环境科学与工程类"],
    "化学工程类": ["化学工程与技术", "化工与制药类"],
    "材料科学与工程类": ["材料科学与工程", "材料类"],
    "矿业工程类": ["矿业工程", "矿业类"],
    "安全工程类": ["安全科学与工程", "安全科学与工程类"],
    "食品科学与工程类": ["食品科学与工程", "食品科学与工程类"],
    "生物工程类": ["生物工程", "生物工程类"],
    "公安技术类": ["公安技术", "公安技术类"],
    "公安学类": ["公安学", "公安学类"],
    "法学类": ["法学", "法学类", "法律"],
    "法律类": ["法学", "法律", "法学类"],
    "社会学类": ["社会学", "社会学类", "社会工作"],
    "社会保障类": ["公共管理类", "社会工作", "劳动与社会保障"],
    "公共管理学类": ["公共管理", "公共管理类", "公共管理学"],
    "公共管理类": ["公共管理类", "公共管理", "公共事业管理", "行政管理",
                 "劳动与社会保障", "土地资源管理", "城市管理"],
    "工商管理类": ["工商管理类", "工商管理", "会计学", "财务管理", "审计学",
                 "国际商务", "人力资源管理", "市场营销", "资产评估"],
    "管理科学与工程类": ["管理科学与工程", "管理科学与工程类", "工程管理", "信息管理与信息系统"],
    "工程管理类": ["管理科学与工程", "工程管理", "管理科学与工程类"],
    "图书情报类": ["图书情报与档案管理", "图书情报", "图书情报与档案管理类"],
    "农业管理类": ["农业管理", "农林经济管理", "农业经济管理类"],
    "心理学类": ["心理学", "心理学类", "应用心理"],
    "教育学类": ["教育学", "教育学类", "教育"],
    "体育学类": ["体育学", "体育学类", "体育"],
    "中国语言文学类": ["中国语言文学", "中国语言文学类"],
    "新闻与传播类": ["新闻传播学", "新闻与传播", "新闻传播学类"],
    "新闻传播学类": ["新闻传播学", "新闻与传播", "出版", "新闻传播学类"],
    "外国语言文学类": ["外国语言文学", "外国语言文学类", "翻译"],
    "历史学类": ["中国史", "世界史", "考古学", "历史学类"],
    "数学类": ["数学", "数学类"],
    "统计学类": ["统计学", "统计学类", "应用统计"],
    "生物学类": ["生物学", "生物科学类"],
    "地理学类": ["地理学", "地理科学类"],
    "植物保护类": ["植物保护", "植物生产类"],
    "园艺学类": ["园艺学", "植物生产类"],
    "作物学类": ["作物学", "植物生产类"],
    "兽医学类": ["兽医学", "动物医学类", "兽医"],
    "动物医学类": ["动物医学类", "兽医学", "兽医"],
    "林学类": ["林学", "林学类", "林业"],
    "水产类": ["水产", "水产类"],
    "中医学类": ["中医", "中医学", "中医学类", "中西医结合"],
    "中药学类": ["中药", "中药学", "中药学类"],
    "药学类": ["药学", "药学类", "药学"],
    "护理类": ["护理", "护理学", "护理学类"],
    "临床医学类": ["临床医学", "临床医学类"],
    "公共卫生类": ["公共卫生与预防医学", "公共卫生", "公共卫生与预防医学类"],
    "医学技术类": ["医学技术", "医学技术类"],
    "艺术学类": ["艺术学理论", "音乐与舞蹈学", "戏剧与影视学", "美术学", "设计学",
               "艺术", "艺术学理论类", "音乐与舞蹈学类", "戏剧与影视学类",
               "美术学类", "设计学类"],
    "设计学类": ["设计学", "设计学类", "设计"],
    "美术学类": ["美术学", "美术学类", "美术与书法"],
    "音乐与舞蹈学类": ["音乐与舞蹈学", "音乐与舞蹈学类", "音乐", "舞蹈"],
    "戏剧与影视学类": ["戏剧与影视学", "戏剧与影视学类", "戏剧与影视"],
    "马克思主义理论类": ["马克思主义理论", "马克思主义理论类"],
    "政治学类": ["政治学", "政治学类"],
    "民族学类": ["民族学", "民族学类"],
    "哲学类": ["哲学", "哲学类"],
    "人民武装": ["人民武装"],
    "国际贸易": ["应用经济学", "国际商务", "经济与贸易类", "国际贸易学"],
    "学科教学": ["教育", "教育学", "教育学类"],
    "风景园林规划与设计": ["风景园林学", "风景园林", "城乡规划学", "建筑类"],
    "劳动法学": ["法学", "法学类", "法律"],
    "社会保障法学": ["法学", "法学类", "法律", "社会工作"],
    "超声医学": ["临床医学", "临床医学类", "医学技术"],
    "放射影像学": ["临床医学", "临床医学类", "医学技术"],
    "影像医学与核医学": ["临床医学", "临床医学类"],
    "农艺与种业": ["农业", "作物学", "植物生产类", "园艺学"],
    "资源利用与植物保护": ["农业", "植物保护", "植物生产类", "农业资源与环境"],
    "畜牧": ["畜牧学", "动物生产类"],
    "思政": ["马克思主义理论", "马克思主义理论类", "思想政治教育"],
    "语文": ["中国语言文学", "中国语言文学类", "学科教学"],
    "统计": ["统计学", "统计学类", "应用统计"],
    "新一代电子信息技术": ["电子信息", "电子信息类", "电子科学与技术"],
    "党的学说与党的建设": ["中共党史党建学", "中共党史党建学类"],
    "工学": [], "管理学": [],  # 由门类映射补全（见 menlei 别名注册）
    "管理": [],  # 同上：岗位要求「管理」按管理学门类展开
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_token(token: str) -> str:
    text = CODE_RE.sub("", token.strip()).strip()
    # v2：剥「1.」类序号前缀
    text = ENUM_PREFIX_RE.sub("", text).strip()
    # v2：剥与中文连写的 4 位学科代码前缀/后缀（0301法学 / 法学类0301）
    text = CODE4_PREFIX_RE.sub("", text).strip()
    text = re.sub(r"(?<=[\u4e00-\u9fff])\d{4,6}[A-Za-z]?$", "", text).strip()
    prev = None
    while prev != text and text:
        prev = text
        text = TAIL_RE.sub("", text)
        text = MASTERS_TAIL_RE.sub("", text)
    return text


def parse_zy(zy: str) -> tuple[list[str], bool]:
    """返回（归一 token 列表, 是否专业不限）。"""
    text = str(zy or "").strip()
    if not text:
        return [], False
    for prefix in ("本科：", "研究生：", "大专：", "本科:", "研究生:", "大专:"):
        text = text.replace(prefix, "、")
    tokens = []
    unlim = False
    for raw in SPLIT_RE.split(text):
        token = clean_token(raw)
        if not token:
            continue
        if UNLIM_RE.search(token):
            unlim = True
            continue
        tokens.append(token)
    return tokens, unlim


def build(catalog_map: dict, rows: list) -> dict:
    catalog_map = dict(catalog_map)
    # 合成自类：岗位原文直接要求「人民武装」专业（专科目录外特例），自指成类，
    # 用户搜「人民武装」走 explicit 命中，不误挂到其他类
    catalog_map.setdefault("人民武装", ["人民武装"])
    member_classes: dict[str, list[str]] = {}
    for major, classes in catalog_map.items():
        names = classes if isinstance(classes, list) else [classes]
        member_classes[str(major).strip()] = [str(c).strip() for c in names]
    class_members: dict[str, list[str]] = collections.defaultdict(list)
    for major, classes in member_classes.items():
        for cl in classes:
            class_members[cl].append(major)
    lowered_members = {name.lower(): name for name in member_classes}
    lowered_classes = {name.lower(): name for name in class_members}

    # v2：目录存在性过滤（映射目标类必须真实存在于目录，宁缺勿错）
    def existing(names: list[str]) -> list[str]:
        seen, out = set(), []
        for n in names:
            key = n.lower()
            if key in lowered_classes and key not in seen:
                seen.add(key)
                out.append(lowered_classes[key])
        return out

    code4_map = {code: existing(names) for code, names in CODE4_TO_CLASSES.items()}
    code4_map = {k: v for k, v in code4_map.items() if v}
    menlei_map = {name: existing(names) for name, names in MENLEI_TO_CLASSES.items()}
    menlei_map = {k: v for k, v in menlei_map.items() if v}
    # 裸门类名（无「门类」后缀）：工学/管理学 等同门类展开
    for base in ("哲学", "经济学", "法学", "教育学", "文学", "历史学", "理学",
                 "工学", "农学", "医学", "管理学", "艺术学"):
        target = menlei_map.get(f"{base}门类")
        if target:
            menlei_map.setdefault(base, target)
    alias_map = {name: existing(names) for name, names in ALIAS_TO_CLASSES.items()}
    alias_map = {k: v for k, v in alias_map.items() if v}
    # 「管理」泛称按管理学门类展开（岗位 zy 常见单写「管理」）
    if menlei_map.get("管理学门类"):
        alias_map.setdefault("管理", menlei_map["管理学门类"])

    explicit: dict[str, list[str]] = collections.defaultdict(list)
    by_class: dict[str, list[str]] = collections.defaultdict(list)
    unlimited: list[str] = []
    unclassified: collections.Counter = collections.Counter()

    def add_class_jobs(job_id: str, class_names: list[str]) -> None:
        for cl in class_names:
            by_class[cl].append(job_id)

    for row in rows:
        job_id = str(row.get("job_id") or row.get("code") or "")
        tokens, unlim = parse_zy(row.get("zy"))
        if unlim:
            unlimited.append(job_id)
        for token in tokens:
            low = token.lower()
            if token in STOPWORDS:
                continue  # 解析噪音：真实专业在同 zy 其他 token
            if token.startswith("不含"):
                continue  # 排除语（不含统计等）：正向专业在同 zy 其他 token
            if low in lowered_members:
                explicit[lowered_members[low]].append(job_id)
                continue
            if low in lowered_classes:
                by_class[lowered_classes[low]].append(job_id)
                continue
            # v2：4 位学科代码（独立 token）
            if CODE4_STANDALONE_RE.match(token) and token in code4_map:
                add_class_jobs(job_id, code4_map[token])
                continue
            # v2：门类名展开
            if token in menlei_map:
                add_class_jobs(job_id, menlei_map[token])
                continue
            # v2：自定义类名别名
            if token in alias_map:
                add_class_jobs(job_id, alias_map[token])
                continue
            # v2：回退——剥尾部「类」再「学类」逐级重查（生态学类→生态学✓ 优先于 生态）
            candidates = []
            if token.endswith("类"):
                candidates.append(token[:-1])
                if token.endswith("学类"):
                    candidates.append(token[:-2])
            matched_fallback = False
            for stripped in candidates:
                if not stripped or stripped == token:
                    continue
                slow = stripped.lower()
                if slow in lowered_classes:
                    by_class[lowered_classes[slow]].append(job_id)
                    matched_fallback = True
                    break
                if slow in lowered_members:
                    explicit[lowered_members[slow]].append(job_id)
                    matched_fallback = True
                    break
            if matched_fallback:
                continue
            unclassified[token] += 1

    def dedup(values: list[str]) -> list[str]:
        return sorted(set(values))

    majors = [
        {"key": name, "classes": member_classes[name], "jobs_explicit": len(dedup(explicit.get(name, [])))}
        for name in sorted(member_classes)
        if explicit.get(name)
    ]
    classes = [
        {"key": name, "members": sorted(class_members[name]), "jobs_by_class": len(dedup(by_class.get(name, [])))}
        for name in sorted(class_members)
        if by_class.get(name)
    ]
    total = len(rows)
    touched = len(
        set().union(*[set(v) for v in explicit.values()], *[set(v) for v in by_class.values()], set(unlimited) or set())
    ) if (explicit or by_class or unlimited) else 0
    return {
        "schema": "wanyu-major-index/v2",
        "majors": majors,
        "classes": classes,
        "postings": {
            "explicit": {k: dedup(v) for k, v in sorted(explicit.items())},
            "by_class": {k: dedup(v) for k, v in sorted(by_class.items())},
            "unlimited": dedup(unlimited),
        },
        "unclassified_tokens": [{"token": token, "jobs": count} for token, count in unclassified.most_common()],
        "stats": {
            "rows": total,
            "rows_touched": touched,
            "rows_unclassified_only": total - touched,
            "explicit_terms": len(explicit),
            "class_terms": len(by_class),
            "unlimited_jobs": len(dedup(unlimited)),
            "menlei_expansions": len(menlei_map),
            "alias_mappings": len(alias_map),
            "code4_mappings": len(code4_map),
        },
        "maps": {"code4": code4_map, "menlei": menlei_map, "alias": alias_map},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="构建专业匹配倒排索引 major-index.json（v2）")
    parser.add_argument("--cycle", default="2026")
    args = parser.parse_args()

    catalog = load_json(HERE / "data" / "major_catalog.json")
    # RC3(O) 输入图纯化：行源=canonical 周期包（生成物 jobs.json 不得作为正式输入）
    sys.path.insert(0, str(HERE.parents[1]))
    from tools.anhui_web.unified_cycle_bundle import load_canonical_doc

    jobs_path = HERE.parents[1] / "canonical" / "cycles" / f"{args.cycle}.json"
    doc = load_canonical_doc(HERE.parents[1], str(args.cycle))
    rows = doc["all_majors"]["rows"]
    # 生命周期口径：只有 active 行进入用户索引（与前端 rowsFor 一致）
    rows = [r for r in rows if not r.get("record_status") or r.get("record_status") == "active"]
    index = build(catalog["map"], rows)
    index["cycle"] = str(args.cycle)
    index["computed_from"] = {"jobs_sha256": sha256(jobs_path), "source": "canonical/cycles"}

    out_path = SITE / "data" / "cycles" / str(args.cycle) / "major-index.json"
    out_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    stats = index["stats"]
    print(f"[{args.cycle}] major-index.json v2 → {out_path.name}（{out_path.stat().st_size/1024:.0f}KB）")
    print(f"  岗位 {stats['rows']} | 触达 {stats['rows_touched']} | 仅未归类 {stats['rows_unclassified_only']} ({stats['rows_unclassified_only']/max(stats['rows'],1)*100:.1f}%)")
    print(f"  explicit 词条 {stats['explicit_terms']} | by_class 词条 {stats['class_terms']} | 不限 {stats['unlimited_jobs']} 岗")
    print(f"  门类展开 {stats['menlei_expansions']} | 别名映射 {stats['alias_mappings']} | 学科代码 {stats['code4_mappings']}")
    top_unc = index["unclassified_tokens"][:5]
    print(f"  未归类Top5: {[(t['token'], t['jobs']) for t in top_unc]}")

    # 验收探针
    p = index["postings"]
    probe = lambda name: (len(p["explicit"].get(name, [])), len(p["by_class"].get(name, [])))
    ip, lc = probe("知识产权")[0], len(set(p["explicit"].get("知识产权", [])) | set(p["by_class"].get("法学类", [])))
    se, jc = probe("软件工程")[0], len(set(p["explicit"].get("软件工程", [])) | set(p["by_class"].get("计算机类", [])))
    kj = len(p["explicit"].get("会计学", []))
    kj_union = len(set(p["explicit"].get("会计学", [])) | set(p["by_class"].get("财会审计类", []) if "财会审计类" in p["by_class"] else set()))
    print(f"  验收: 知识产权 explicit={ip} ∪法学类={lc} | 软件工程 explicit={se} ∪计算机类={jc} | 会计学 explicit={kj} ∪财会审计类={kj_union}")
    ok = lc >= 1100 and jc >= 500 and kj >= 800
    print("  RESULT:", "PASS" if ok else "CHECK-TRESHOLDS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
