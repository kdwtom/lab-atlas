"""Parser tests for the phase 3 universities, using fragments copied from the real pages (structure as of 2026-11)."""
from pipeline.lib.faculty import hanyang, korea, skku, sogang, yonsei

YONSEI_CARD = """<div class="professor"><div class="board-faculty-box"><dl><dt> Kim, Seick </dt>
<dd><span>김세익 (학과장)</span></dd><dd><a href="mailto:kimseick@yonsei.ac.kr">kimseick@yonsei.ac.kr</a></dd>
<dd>과학관 216 (Tel: 2587)</dd><dd><a href="https://kimseick.yonsei.ac.kr/">Personal Website</a></dd><dd>PDE, Analysis</dd></dl></div>
<div class="board-faculty-box"><dl><dt> 강태건 </dt><dd><span>Assistant Professor</span></dd>
<dd><a href="mailto:TGK@YONSEI.AC.KR">TGK@YONSEI.AC.KR</a></dd><dd>02-2123-2706</dd>
<dd><a href="https://sites.google.com/view/kangslab/home">🌐중개면역 연구실</a></dd><dd>323동 과학원 S421</dd></dl></div></div>"""

YONSEI_CS = """<table class="yonsei-table"><tbody><tr><td><img/></td><td><p><span>황성재 (인공지능학과장)</span></p></td>
<td> 컴퓨터 비전, 머신러닝</td><td><span><a href="https://micv.yonsei.ac.kr/"><u>의료영상분석및비전</u></a></span></td></tr></tbody></table>"""

KOREA = """<div class="pro_list"><div><a class="modaltrigger" href="#modal"><dl><dt> 강세종 Kahng, Se-Jong </dt><dd>교수</dd>
<dd class="field">연구분야 : 통계 물리학, 복잡한 네트워크</dd><dd>전화번호 : 02-3290-3109</dd></dl></a></div>
<div><a class="modaltrigger" href="#modal"><dl><dt> 강태호 교수 </dt><dd></dd><dd class="field">연구분야 : Organic, Polymer</dd></dl></a></div>
<div><a href="?mode=view&amp;articleNo=755116"><dl><dt>강성구</dt><dd>seongkukang@korea.ac.kr</dd><dd>https://idea.korea.ac.kr/</dd>
<dd>데이터과학 및 응용 연구실 (Intelligent Data Science and Applications Lab)</dd></dl></a></div></div>
<div class="pro_list_box"><div><dl><dt>고영규 </dt><dd><b> 전공분야 </b><br/>세포생물학, 텍사스대(1994)</dd><dd><b>직위:</b> 교수</dd></dl></div></div>"""

SKKU = """<div class="faculty-info-box"><dl><dt><a class="faculty-link" href="?mode=view&amp;perId=ABC &amp;">img</a></dt>
<dd><ul><li><span class="jg">교수</span><span class="dtj">분자신경유전학</span></li>
<li><span>권재영</span><a href="https://sites.google.com/view/neurogenetics-skku/home "></a><div class="lab-div">
<a class="profLabIcon" href="https://sites.google.com/view/neurogenetics-skku/home"> Lab </a><span>신경유전학 연구실</span></div></li></ul></dd>
<dd><ul><li class="mail"><a href="mailto:jykwon@skku.edu">jykwon@skku.edu</a></li></ul></dd></dl></div>
<div class="faculty-info-box"><dl><dd><ul><li><span class="jg">명예교수</span></li><li><span>홍길동</span></li></ul></dd></dl></div>"""

HANYANG = """<div class="hyu-profile-inner"><h4 class="hyu-profile-info-title-name">Kim, Sun-Woo</h4>
<div class="hyu-profile-info-title-position"><p>김선우</p></div><div class="hyu-profile-info-desc"><p>Assistant Professor</p></div>
<ul class="hyu-profile-info-contact"><li><a href="mailto:sunwookim@hanyang.ac.kr">m</a></li>
<li><a href="https://sites.google.com/view/qmilabhyu/home">h</a></li></ul></div>
<div class="hyu-profile-inner"><h4 class="hyu-profile-info-title-name">윤소원 교수</h4>
<div class="hyu-profile-info-title-position"><p>교수 (학과장)</p></div><div class="hyu-profile-info-desc"><p>연구영역: 유기화학, 유기반응</p></div></div>
<div class="hyu-profile-inner"><h4 class="hyu-profile-info-title-name">신상진</h4>
<div class="hyu-profile-info-title-position"><p>Honorary Professor</p></div></div>
<div class="hyu-profile-inner"><h4 class="hyu-profile-info-title-name">오창호 교수</h4>
<div class="hyu-profile-info-title-position"><p>교수</p></div><div class="hyu-profile-info-desc"><p>정년퇴임일 - 2024.08</p></div></div>
<div class="hyu-profile-inner"><h4 class="hyu-profile-info-title-name">Lee, Won-wook</h4>
<div class="hyu-profile-info-title-position"><p>이원욱</p></div><div class="hyu-profile-info-desc"><p>Professor (teaching)</p></div></div>"""

SOGANG_PHYS = """<div class="sgp"><article class="sgp-card sgp-person"><div class="sgp-person-body"><h4>김 도 석<small>Doseok KIM</small></h4>
<ul aria-label="연구분야"><li class="sgp-tag">광학</li><li class="sgp-tag">응집물리실험</li></ul><dl class="sgp-kv"><dt>연구실</dt>
<dd>R1025 · <a href="http://smos.sogang.ac.kr/">연성물질 분광학 연구실 <span>↗</span></a></dd><dt>이메일</dt>
<dd><a href="mailto:doseok@sogang.ac.kr">doseok@sogang.ac.kr</a></dd></dl></div></article></div>"""

SOGANG_CS = """<script>window.__NUXT__=(function(a,b,c,d){return {data:[{PROF_LIST:[
{LAB_NM:"금융기계학습 연구실",HMPG_URL_ADDR:"http:\\u002F\\u002Ffml.sogang.ac.kr",EML_ADDR:"saejoon@sogang.ac.kr",MJR_FLD_NM:"기계학습, 금융경제학",PROF_SE_NM:a,EDC_DEPT_PROF_GRP_SN:c,PROF_INFO_OTPT_SE_CD:b,PROF_NM:"김세준"},
{LAB_NM:a,EML_ADDR:"x@sogang.ac.kr",PROF_SE_NM:"명예교수",EDC_DEPT_PROF_GRP_SN:d,PROF_INFO_OTPT_SE_CD:b,PROF_NM:"박석"},
{LAB_NM:a,EML_ADDR:"y@sogang.ac.kr",PROF_SE_NM:a,EDC_DEPT_PROF_GRP_SN:d,PROF_INFO_OTPT_SE_CD:b,PROF_NM:"최명환"}]}]}}("교수","DGR",123,125));</script>"""


def test_yonsei_cards_both_name_orders():
    rs = yonsei.parse_cards(YONSEI_CARD, "https://math.yonsei.ac.kr/x")
    assert (rs[0]["name_ko"], rs[0]["name_en"]) == ("김세익", "Seick Kim")
    assert rs[0]["research_fields"] == ["PDE", "Analysis"] and rs[0]["lab_name"] is None
    assert rs[1]["name_ko"] == "강태건" and rs[1]["position_raw"] == "Assistant Professor"
    assert rs[1]["lab_name"] == "중개면역 연구실" and rs[1]["email"] == "tgk@yonsei.ac.kr"


def test_yonsei_cs_strips_role():
    r = yonsei.parse_cs(YONSEI_CS, "https://cs.yonsei.ac.kr/x")[0]
    assert r["name_ko"] == "황성재" and r["research_fields"] == ["컴퓨터 비전", "머신러닝"]


def test_korea_cms_variants():
    rs = korea.parse(KOREA, "https://physics.korea.ac.kr/x")
    by = {r["name_ko"]: r for r in rs}
    assert by["강세종"]["name_en"] == "Se-Jong Kahng" and by["강세종"]["position_raw"] == "교수"
    assert by["강태호"]["research_fields"] == ["Organic", "Polymer"]
    assert by["강성구"]["email"] == "seongkukang@korea.ac.kr" and by["강성구"]["lab_name"].startswith("데이터과학")
    assert "mode=view" in by["강성구"]["faculty_page_url"]
    assert by["고영규"]["research_fields"] == ["세포생물학"]


def test_skku_skips_emeritus():
    rs = skku.parse(SKKU, "https://cscience.skku.edu/x")
    assert [r["name_ko"] for r in rs] == ["권재영"]
    assert rs[0]["lab_name"] == "신경유전학 연구실" and not rs[0]["faculty_page_url"].endswith("&")


def test_hanyang_keeps_full_time_only():
    rs = hanyang.parse(HANYANG, "https://physics.hanyang.ac.kr/faculty")
    assert [(r["name_ko"], r["name_en"]) for r in rs] == [("김선우", "Sun-Woo Kim"), ("윤소원", None)]
    assert rs[1]["research_fields"] == ["유기화학", "유기반응"]


def test_sogang_phys_spaced_name():
    r = sogang.parse_phys(SOGANG_PHYS, "https://physics.sogang.ac.kr/x")[0]
    assert (r["name_ko"], r["name_en"]) == ("김도석", "Doseok Kim")
    assert r["lab_name"] == "연성물질 분광학 연구실"


def test_sogang_cs_nuxt_payload_drops_emeritus_group():
    rs = sogang.parse_cs(SOGANG_CS, "https://computing.sogang.ac.kr/x")
    assert [r["name_ko"] for r in rs] == ["김세준"]
    assert rs[0]["homepage_url"] == "http://fml.sogang.ac.kr"
