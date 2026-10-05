import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAtlas } from '../data/DataContext';
import { ISSUE_URL, fmtDate } from '../lib/format';

export default function AboutPage() {
  const { meta, clusters } = useAtlas();
  const { hash } = useLocation();
  const sc = meta.summary_coverage;
  const [y0, y1] = meta.window_years;

  useEffect(() => {
    document.title = '방법론 · Lab Atlas';
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
    else window.scrollTo(0, 0);
  }, [hash]);

  return (
    <main className="page about">
      <p className="crumb"><Link to="/">← 지형도</Link></p>
      <h1>방법론</h1>
      <p className="lead">
        Lab Atlas는 대학원 진학을 고민하는 학생이 비슷한 연구를 하는 연구실을 한눈에 비교할 수 있도록,
        국내 6개 생명과학 학과의 연구실을 공개 논문 데이터로 배치한 지형도입니다. 모든 정보는 API 응답이나
        공식 웹페이지에서 가져왔고, 확인할 수 없는 항목은 “정보 없음”으로 표시합니다.
      </p>

      <section>
        <h2>대상과 선정 기준</h2>
        <ul>
          <li>대상 학과: KAIST 생명과학과, 서울대학교 생명과학부, POSTECH 생명과학과, UNIST 생명과학과, GIST 생명과학과, DGIST 뉴바이올로지학과.</li>
          <li>각 학과 교수진 페이지에 <strong>현재 전임교원</strong>(교수·부교수·조교수)으로 등재된 교수만 포함합니다. 명예·겸임·초빙·연구교수 등은 제외했습니다.</li>
          <li>
            {y0}–{y1}년(수집 연도 포함 최근 5년)에 <strong>마지막 저자 또는 교신저자</strong>로 참여한 논문(OpenAlex 유형 article·review)이{' '}
            <strong>{meta.min_senior_papers}편 이상</strong>인 연구실만 표시합니다.
          </li>
          <li>현재 {meta.counts.labs}개 연구실, 논문 {meta.counts.papers.toLocaleString()}편이 지형도에 있습니다.</li>
        </ul>
      </section>

      <section>
        <h2>데이터 출처</h2>
        <ul>
          <li><strong>학과 교수진 페이지</strong>: 이름(한/영), 직위, 연구실 이름·홈페이지. POSTECH·UNIST는 학과 사이트에 접속할 수 없어 대학 공식 연구자 검색(학과 필터)을 사용했습니다.</li>
          <li><strong>OpenAlex</strong>: 저자 정보, 논문 메타데이터(제목, 연도, 학술지, DOI, 인용 수, 저자 순서·교신 여부, 주제).</li>
          <li><strong>Semantic Scholar</strong>: 논문별 TLDR(가능한 경우, 요약 작성의 보조 근거).</li>
          <li>각 연구실 상세 페이지에 출처 URL과 수집 날짜를 표시합니다. 사이트는 실행 중에 어떤 API도 호출하지 않습니다.</li>
        </ul>
      </section>

      <section>
        <h2>OpenAlex 매칭과 제외 방식</h2>
        <p>동명이인을 피하기 위해 교수진 페이지의 교수를 OpenAlex 저자와 다음 근거로 교차 확인했습니다.</p>
        <ul>
          <li><strong>소속</strong>: 해당 대학이 최근 3년 이내 소속 이력에 있어야 합니다.</li>
          <li><strong>이름</strong>: 영문 이름 토큰 일치(어순·하이픈·중간 이니셜 무시). 영문명이 없으면 한글 성과 이름의 로마자 표기(국어의 로마자 표기법·관용 표기 변형)를 비교합니다.</li>
          <li><strong>주제</strong>: 저자의 상위 주제 중 생명과학(Life Sciences) 비율 40% 이상.</li>
          <li><strong>대표 논문</strong>: 교수진 페이지에 실린 논문(최대 8편)을 OpenAlex에서 찾아 실제 저자인지 확인합니다.</li>
          <li><strong>ORCID</strong>: 교수진 페이지에 있으면 최우선으로 사용합니다.</li>
        </ul>
        <p>
          조건을 모두 만족하는 후보가 정확히 한 명일 때만 매칭합니다. 여러 명이면 대표 논문이 한 후보를 가리키거나,
          OpenAlex의 동일인 분할 프로필로 판단될 때(작은 쪽 논문 수가 큰 쪽의 10% 이하)만 선택하고, 그 외에는 제외합니다.
          대표 논문으로 확인된 매칭은 신뢰도 “높음”, 그 외는 “보통”으로 표시합니다. 제외된 교수와 사유는 저장소의
          <code>pipeline/output/excluded.csv</code>에 기록되어 있습니다.
        </p>
        <p>
          <strong>동명이인 논문 정리</strong>: OpenAlex 저자 프로필에는 같은 이름의 다른 연구자 논문이 섞이는 경우가 있습니다.
          그래서 (1) 유사도·키워드·대표 논문 분석에는 PI의 소속이 해당 대학이거나 소속이 기재되지 않은 논문만 사용하고,
          (2) 논문 내용이 연구실의 다른 논문들과 동떨어진 경우를 임베딩 거리로 골라 제목과 학술지를 사람이 검토해 PI 연구 분야와
          명백히 다른 분야(임상의학, 공학, 사회과학 등)의 논문 <strong>{meta.excluded_namesake_papers}편</strong>을 기준 판정과 분석 모두에서 제외했습니다.
        </p>
      </section>

      <section>
        <h2>유사도, 공동연구, 클러스터</h2>
        <ul>
          <li>연구실별로 최근 논문 최대 30편(마지막·교신저자 논문 우선)의 제목과 초록을 <code>allenai-specter</code> 모델로 임베딩하고, 인용 수에 로그 가중치(1 + ln(1 + 인용 수))를 준 평균을 연구실 벡터로 썼습니다.</li>
          <li>
            <strong>연구 주제 유사도 선</strong>: 연구실 벡터의 코사인 유사도에서 각 연구실의 상위 {meta.similarity_k ?? 5}개 이웃 중
            임계값 {meta.similarity_threshold?.toFixed(4) ?? '정보 없음'}(상위 이웃 유사도 분포의 하위 25% 지점)을 넘는 쌍만 남겼습니다.
            “연결 이유”는 두 연구실 논문에 공통으로 나타나는 OpenAlex 주제 중 비중이 큰 최대 3개입니다.
          </li>
          <li><strong>공동연구 선</strong>: 지형도 안의 두 PI가 함께 저자로 참여한 논문 수입니다.</li>
          <li>
            <strong>클러스터</strong>: 유사도 이웃 그래프에 Louvain 커뮤니티 탐지(random seed {meta.louvain_seed ?? '정보 없음'})를 적용했고,
            클러스터가 6–12개가 되는 resolution 중 {meta.louvain_resolution ?? '정보 없음'}을 선택해 {clusters.length}개로 나눴습니다.
            라벨은 대표 키워드와 소속 연구실을 보고 직접 붙였습니다.
          </li>
          <li>노드의 처음 위치는 연구실 벡터를 UMAP으로 2차원에 투영한 좌표이며, 같은 클러스터끼리 약하게 모이는 힘을 더했습니다.</li>
        </ul>
      </section>

      <section>
        <h2>대표 논문 선정 규칙</h2>
        <p>
          PI가 마지막 저자 또는 교신저자이고 초록이 있는 논문만 후보로 하며, 연간 인용 수(인용 수 ÷ 출판 후 경과 연수, 최소 1년)로
          정렬해 3편을 고릅니다. 단, 최근 2년 이내 논문을 최소 1편 포함합니다. 후보가 3편보다 적으면 있는 만큼만 표시합니다.
        </p>
      </section>

      <section>
        <h2>요약 작성 방식</h2>
        <p>
          대표 논문의 한국어 요약(한 줄 요약, 연구 배경, 방법, 핵심 발견, 의의)과 연구실 소개는 AI 언어 모델(Anthropic Claude)이
          초록·TLDR·논문 목록만을 근거로 작성했고, 무작위 표본을 원래 초록과 대조해 근거 없는 주장이 없는지 점검했습니다. 초록에서 근거를 찾을 수 없는 항목은 “초록에서 확인 불가”로 두었고, 전문 용어는 처음 나올 때 영문을
          병기했습니다. 저작권을 고려해 <strong>초록 원문은 게재하지 않으며</strong>, 원문은 DOI 링크로 확인할 수 있습니다.
        </p>
        {sc && (
          <p className="notice">
            현재 작성 현황: 대표 논문 {sc.representative_papers}편 중 <strong>{sc.papers_with_summary}편</strong>,
            연구실 {sc.labs}곳 중 <strong>{sc.labs_with_intro}곳</strong>의 소개가 작성되었습니다. 나머지는 “정보 없음”으로 표시되며 순차적으로 보완할 예정입니다.
          </p>
        )}
      </section>

      <section>
        <h2>한계와 면책</h2>
        <ul>
          <li>OpenAlex의 저자 식별과 소속·교신저자 정보에는 오류나 누락이 있을 수 있으며, 그 결과 일부 연구실의 논문 수가 실제와 다르거나 기준에서 빠졌을 수 있습니다.</li>
          <li>최근 5년·마지막/교신저자 기준은 신임 교수나 논문 발표 방식이 다른 분야에 불리할 수 있습니다. 지형도에 없다고 해서 연구 활동이 적다는 뜻은 아닙니다.</li>
          <li>유사도와 클러스터는 논문 텍스트에 기반한 근사치이며, 연구실의 실제 연구 방향·분위기·모집 계획을 나타내지 않습니다.</li>
          <li>요약은 AI가 초록을 바탕으로 작성했으므로 오류가 있을 수 있습니다. 진학 결정 전에는 반드시 연구실 홈페이지와 원문 논문을 확인하세요.</li>
          <li>이 사이트는 각 대학·학과와 무관한 개인 프로젝트이며, 교수 사진은 사용하지 않습니다.</li>
        </ul>
      </section>

      <section>
        <h2>업데이트</h2>
        <p>데이터 수집일 {fmtDate(meta.data_retrieved_at)} · 사이트 데이터 생성일 {fmtDate(meta.generated_at)}</p>
      </section>

      <section id="correction">
        <h2>정보 수정 요청</h2>
        <p>
          잘못된 정보나 누락된 연구실이 있다면 <a href={ISSUE_URL} target="_blank" rel="noreferrer">GitHub Issue</a>로 알려 주세요.
          연구실 이름(또는 PI 이름), 대학, 수정할 내용과 근거 URL을 함께 적어 주시면 다음 데이터 갱신 때 반영합니다.
        </p>
      </section>
    </main>
  );
}
