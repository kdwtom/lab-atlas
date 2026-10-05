"""Parser tests using HTML fragments copied from the real pages (structure as of 2026-10)."""
from pipeline.lib.faculty import dgist, gist, kaist, postech, snu, unist

KAIST_LIST = """<div id="prof"><ul class="prof-list mt-50">
<li><a href="#view" onclick="fn_selectDoc('9727');"><div class="prof-wrap"><div class="prof-info"><ul>
<li class="prof-name">Suk-Jo Kang (강석조)</li><li class="prof-type">Associate Professor</li>
<li>Tel : 042-350-2611 </li><li>Email : suk-jo.kang@kaist.ac.kr</li></ul></div></div></a></li>
<li><a href="#view" onclick="fn_selectDoc('9800');"><div class="prof-info"><ul>
<li class="prof-name">Sung Ik, Cho (조성익)</li><li class="prof-type">Assistant Professor</li></ul></div></a></li>
</ul></div>"""

KAIST_DETAIL = """<div id="profile"><div class="prof_inner"><div class="in_txt"><span>Biochemistry</span><h1>강석조</h1>
<h2 class=""><small>Suk-Jo Kang</small><span>Associate Professor</span></h2></div>
<div class="in_cont"><div class="row"><p class="title">LAB&nbsp;</p><div> Molecular and Cellular Immunology Lab </div></div>
<div class="row"><p class="title">Research Area&nbsp;</p><ul><li>Cancer Biology (암생물학)</li><li> Immunology (면역학)</li></ul></div></div>
<div class="h_page"><a href="https://sites.google.com/site/mcikaist/" target="_blank"><span>WEBSITE</span></a></div></div></div>"""

SNU_LIST = """<div><article class="portfolio-item facultyitem"><div class="portfolio-image">
<a href="/people/faculty?mode=view&profidx=80" class="center-icon"></a></div>
<div class="portfolio-desc center"><h3><a href="/people/faculty?mode=view&profidx=80">강찬희</a><span class="ptit">부교수</span></h3></div></article></div>"""

SNU_DETAIL = """<div class="row faculthead"><div class="heading-block"><span class="before-heading color">부교수</span>
<h3>강찬희 <span class="fs15">Kang, Chanhee</span></h3></div>
<ul class="portfolio-meta nobottommargin prof">
<li><span><i></i>Lab. :</span> 스트레스 반응 및 노화 연구실</li>
<li><span><i></i>Website :</span> <a href="http://biosci.snu.ac.kr/kanglab">http://biosci.snu.ac.kr/kanglab</a></li>
<li><span><i></i>Email :</span> <a href="mailto:chanhee.kang@snu.ac.kr">chanhee.kang@snu.ac.kr</a></li></ul></div>
<div class="row facultycontent"><div class="prof-stit">연구분야</div><div class="prof-wrap"><span class="label label-primary">분자생물학</span></div>
<div class="prof-stit">주요논문</div><div class="prof-wrap"><ol>
<li>Joung J, Kim MS#, and Kang C# (2025) Cell enlargement modulated by GATA4 and YAP instructs the senescence-associated secretory phenotype. <b><i>Nature Communications</i></b> 16:1696</li>
</ol></div></div>"""

POSTECH_LIST = """<p class="total-results">총 <span class="count">29</span>건</p>
<div class="thumb_board_list style3"><ul><li><div class="cont"><div class="top">
<a href="?mode=view&id=fdf7c49c167de224cc78528fcfdcfbe8&pager.offset=0"><p class="tit">김광순 <span></span></p></a></div>
<ul class="info"><li class="type1">생명과학과</li></ul></div></li>
<li><div class="cont"><div class="top"><a href="?mode=view&id=aaaa"><p class="tit">홍길동</p></a></div>
<ul class="info"><li class="type1">시스템생명공학부</li></ul></div></li></ul></div>"""

POSTECH_DETAIL = """<div class="con-box"><h3 class="name">김광순 <span class="rea">부교수</span></h3>
<ul class="nm01"><li class="ic01">생명과학과</li><li class="ic03"><a href="mailto:kskim27@postech.ac.kr">kskim27@postech.ac.kr</a></li>
<li class="ic04"><a href="https://sites.google.com/view/postech-imi-lab/home">x</a></li></ul></div>
<div class="tab_cont con2" id="con2"><ul>
<li>A hierarchy of intestinal antigens instructs the CD4 T cell receptor repertoire, Immunity, , 58, 1217-1235 (2025 )</li>
</ul></div>"""

UNIST_LIST = """<div class="bn-list-prog-researcher type01"><p>총 <span>18</span>건</p><ul><li>
<div class="b-img-box"><a href="https://research.unist.ac.kr/research/faculty/faculty.do?mode=view&profileNo=104" title="강병헌"></a></div>
<div><span>학과</span>생명과학과</div></li>
<li><div class="b-img-box"><a href="https://research.unist.ac.kr/x?profileNo=1" title="다른학과"></a></div><div><span>학과</span>화학과</div></li></ul></div>"""

UNIST_DETAIL = """<div class="researcher-box01"><div class="txt-wrap"><p class="txt01">생명과학과</p><p class="txt02">강병헌</p>
<p class="txt03"><span>교수</span><span>Byoung Heon Kang</span></p>
<ul class="bn-info-box"><li class="ico-mail"><a href="mailto:kangbh@UNIST.AC.KR">kangbh@UNIST.AC.KR</a></li></ul>
<ul class="bn-link-box"><li><a href="?mode=list" title="목록으로 돌아가기">목록</a></li>
<li><a href="https://sites.google.com/site/mitomed/" title="교원 홈페이지 (새 창)">교원 홈페이지</a></li></ul></div></div>"""

GIST_LIST = """<div class="card--body"><strong class="ui-list__title"> 김영준(학과장) </strong><div class="ui-list__txt"><div class="list-gup"><ul class="list-1st">
<li><b>LAB NAME</b><i>분자행동신경학 연구실</i></li><li><b>E-MAIL</b><i>kimyj@gist.ac.kr</i></li></ul></div>
<div class="ui-list__button"><a href="#detail" onclick="fn_search_detail('B000000080044Xs9mY5v'); return false;">Detail</a>
<a href="https://example.org/lab" class="btn btn-danger btn-icon">Homepage</a></div></div></div>"""

GIST_ENG = """<div class="card--body"><strong class="ui-list__title"> KIM Young-Joon (Department Chair) </strong><div class="ui-list__txt"><ul class="list-1st">
<li><b>E-MAIL</b><i>kimyj@gist.ac.kr</i></li></ul></div></div>"""

GIST_DETAIL = """<div>권용훈</div><div>WEBSITE</div><div>https://x</div><div>RESEARCH FIELD</div><div>GPCR signaling</div>
<div>WORK EXPERIENCE</div><div>2023-Present, Assistant Professor, School of Life Science, GIST</div>
<div>REPRESENTATIVE_PUBLICATIONS</div><div>Non-canonical β-adrenergic activation of ERK at endosomes, 2022, Nature</div><div>INTRODUCE</div><div>소개</div>"""

DGIST_LIST = """<div class="ui board--card--list"><div class="obj col3">
<div class="col"><button type="button" class="inner-box button_view"><div class="card--body"><div class="title-wrap"><span class="status status1">전임교원</span>
<strong class="title">June M. Kwak / 곽준명</strong><span class="position">Professor</span></div>
<ul class="list-1st"><li class="info"><span class="tit">Research Field</span><span class="txt">Plant Development</span></li></ul></div></button>
<div class="link-wrap n2"><a href="https://kwaklab.example">홈페이지</a><a href="mailto:jkwak@dgist.ac.kr">이메일</a></div></div>
<div class="col"><button type="button" class="inner-box button_view"><div class="card--body"><div class="title-wrap"><span class="status">명예교수</span>
<strong class="title">Old Prof / 명예인</strong><span class="position">Professor</span></div></div></button></div>
</div></div>"""


def test_kaist():
    rows = kaist.parse_list(KAIST_LIST)
    assert rows[0] == {"name_en": "Suk-Jo Kang", "name_ko": "강석조", "position_raw": "Associate Professor",
                       "email": "suk-jo.kang@kaist.ac.kr", "seq": "9727"}
    assert rows[1]["name_en"] == "Sung Ik, Cho"
    d = kaist.parse_detail(KAIST_DETAIL, "https://bio.kaist.ac.kr/")
    assert d["homepage_url"] == "https://sites.google.com/site/mcikaist/"
    assert d["lab_name"] == "Molecular and Cellular Immunology Lab"
    assert d["research_fields"][0].startswith("Cancer Biology")


def test_snu():
    rows = snu.parse_list(SNU_LIST, "https://biosci.snu.ac.kr/people/faculty")
    assert rows == [{"name_ko": "강찬희", "position_raw": "부교수",
                     "detail_url": "https://biosci.snu.ac.kr/people/faculty?mode=view&profidx=80"}]
    d = snu.parse_detail(SNU_DETAIL, "https://biosci.snu.ac.kr/")
    assert d["name_en"] == "Kang, Chanhee"
    assert d["homepage_url"] == "http://biosci.snu.ac.kr/kanglab"
    assert d["email"] == "chanhee.kang@snu.ac.kr"
    assert len(d["anchor_citations"]) == 1 and "GATA4" in d["anchor_citations"][0]
    assert d["lab_name"] == "스트레스 반응 및 노화 연구실"
    # on the live site the "Lab" row is a phone number, which must not become the lab name
    phone = snu.parse_detail(SNU_DETAIL.replace("스트레스 반응 및 노화 연구실", "02-880-4426"), "https://biosci.snu.ac.kr/")
    assert phone["lab_name"] is None


def test_postech():
    rows, total = postech.parse_list(POSTECH_LIST, "https://www.postech.ac.kr/kor/x.do")
    assert total == 29 and len(rows) == 1 and rows[0]["id"] == "fdf7c49c167de224cc78528fcfdcfbe8"
    d = postech.parse_detail(POSTECH_DETAIL, "https://www.postech.ac.kr/")
    assert d["name_ko"] == "김광순" and d["position_raw"] == "부교수" and d["dept"] == "생명과학과"
    assert d["homepage_url"].startswith("https://sites.google.com/view/postech-imi-lab")
    assert d["anchor_citations"] and "Immunity" in d["anchor_citations"][0]


def test_unist():
    rows, total = unist.parse_list(UNIST_LIST)
    assert total == 18 and [r["name_ko"] for r in rows] == ["강병헌"]
    d = unist.parse_detail(UNIST_DETAIL, "https://research.unist.ac.kr/")
    assert d["name_en"] == "Byoung Heon Kang" and d["position_raw"] == "교수"
    assert d["homepage_url"] == "https://sites.google.com/site/mitomed/"
    assert d["email"] == "kangbh@unist.ac.kr"


def test_gist():
    rows = gist.parse_list(GIST_LIST, "https://life.gist.ac.kr/")
    assert rows[0]["name"] == "김영준" and rows[0]["pid"] == "B000000080044Xs9mY5v"
    assert rows[0]["homepage_url"] == "https://example.org/lab"
    eng = gist.parse_list(GIST_ENG, "https://life.gist.ac.kr/")
    assert gist.english_name(eng[0]["name"]) == "Young-Joon Kim"
    assert gist.english_name("Darren R. Williams") == "Darren R. Williams"
    d = gist.parse_detail(GIST_DETAIL)
    assert d["position_raw"] == "Assistant Professor"
    assert d["anchor_citations"] == ["Non-canonical β-adrenergic activation of ERK at endosomes, 2022, Nature"]


def test_dgist():
    rows = dgist.parse_list(DGIST_LIST, "https://www.dgist.ac.kr/")
    assert rows[0]["name_en"] == "June M. Kwak" and rows[0]["name_ko"] == "곽준명"
    assert rows[0]["status"] == "전임교원" and rows[0]["email"] == "jkwak@dgist.ac.kr"
    assert rows[0]["homepage_url"] == "https://kwaklab.example"
    assert rows[1]["status"] == "명예교수"
