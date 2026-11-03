import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAtlas } from '../data/DataContext';
import { ISSUE_URL, UNIV_LABEL, UNIV_ORDER, fmtDate } from '../lib/format';
import { FIELD_LABEL, FIELD_ORDER } from '../lib/palette';

export default function AboutPage() {
  const { meta, clusters, labs, paperById } = useAtlas();
  const { hash } = useLocation();
  const sc = meta.summary_coverage;
  const [y0, y1] = meta.window_years;

  // Paper summaries are not spread evenly across fields. Computed from the data so this disclosure
  // disappears on its own once the remaining summaries land.
  const gaps = FIELD_ORDER.map((f) => {
    const reps = labs.filter((l) => l.disciplines[0] === f).flatMap((l) => l.representative_paper_ids);
    return { label: FIELD_LABEL[f], total: reps.length, missing: reps.filter((id) => !paperById.get(id)?.summary_ko).length };
  }).filter((g) => g.missing > 0);
  const deptsByUniv = UNIV_ORDER.map((u) => ({ u, depts: meta.departments.filter((d) => d.univ === u) }))
    .filter((g) => g.depts.length > 0);

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
        국내 6개 대학의 생명과학·화학·물리·수학·컴퓨터 학과 연구실을 공개 논문 데이터로 배치한 지형도입니다.
        분야가 달라도 연구 내용이 가까우면 가까이 놓이므로, 바이오정보학처럼 여러 분야에 걸친 연구실을 찾을 수 있습니다. 모든 정보는 API 응답이나
        공식 웹페이지에서 가져왔고, 확인할 수 없는 항목은 “정보 없음”으로 표시합니다.
      </p>

      <section>
        <h2>대상과 선정 기준</h2>
        <ul>
          <li>
            대상 학과({meta.departments.length}개, 괄호는 지형도의 연구실 수):
            <ul>
              {deptsByUniv.map(({ u, depts }) => (
                <li key={u}>
                  {UNIV_LABEL[u]}: {depts.map((d) => `${d.name_ko}(${d.labs})`).join(', ')}
                </li>
              ))}
            </ul>
          </li>
          <li>각 학과 교수진 페이지에 <strong>현재 전임교원</strong>(교수·부교수·조교수)으로 등재된 교수만 포함합니다. 명예·겸임·겸무·초빙·연구·강의전담 교수 등은 제외했습니다. 두 학과에 등재된 교수는 한 연구실로 합치고 학과를 모두 표시합니다.</li>
          <li>
            {y0}–{y1}년(수집 연도 포함 최근 5년)의 논문(OpenAlex 유형 article·review, 컴퓨터는 학회 논문 포함) 수가 분야별 기준을 넘는 연구실만 표시합니다.
            분야마다 저자 순서 관행이 달라 기준도 다릅니다.
            <ul>
              {FIELD_ORDER.filter((f) => meta.rules[f]).map((f) => (
                <li key={f}><strong>{FIELD_LABEL[f]}</strong>: {meta.rules[f]}</li>
              ))}
            </ul>
            수학은 저자를 알파벳 순으로 쓰는 관행이 있어 저자 순서를 보지 않고, 컴퓨터는 이론 분야의 알파벳 순 논문도 인정합니다.
            물리·컴퓨터의 저자 100명 이상 대형 협력 논문은 연구실 고유의 주제로 보기 어려워 집계·분석·공동연구 선에서 모두 뺐습니다.
          </li>
          <li>현재 {meta.counts.labs}개 연구실, 논문 {meta.counts.papers.toLocaleString()}편이 지형도에 있습니다.</li>
        </ul>
      </section>

      <section>
        <h2>데이터 출처</h2>
        <ul>
          <li><strong>학과 교수진 페이지</strong>: 이름(한/영), 직위, 연구실 이름·홈페이지. POSTECH·UNIST는 대학 공식 연구자 검색(학과 필터)을 사용했고, 학과 홈페이지보다 인원이 적을 수 있습니다. DGIST는 화학·물리 대학원 학과가 없어 학부 트랙(화학 트랙, 물리 트랙)의 교수 명단을 썼습니다.</li>
          <li><strong>OpenAlex</strong>: 저자 정보, 논문 메타데이터(제목, 연도, 학술지, DOI, 인용 수, 저자 순서·교신 여부, 주제).</li>
          <li><strong>Semantic Scholar</strong>: 논문별 TLDR(가능한 경우, 요약 작성의 보조 근거).</li>
          <li>각 연구실 상세 페이지에 출처 URL과 수집 날짜를 표시합니다. 사이트는 실행 중에 어떤 API도 호출하지 않습니다.</li>
        </ul>
      </section>

      <section>
        <h2>OpenAlex 매칭과 제외 방식</h2>
        <p>
          자동 매칭 뒤에 의심 사례의 논문 제목을 AI(Claude)가 읽고 16명을 수동으로 고쳤습니다(프로필 교체 10명, 믿을 만한 프로필이 없어 제외 6명).
          내역은 저장소의 <code>pipeline/curation/match_overrides.json</code>에 있습니다.
        </p>
        <p>동명이인을 피하기 위해 교수진 페이지의 교수를 OpenAlex 저자와 다음 근거로 교차 확인했습니다.</p>
        <ul>
          <li><strong>소속</strong>: 해당 대학이 최근 3년 이내 소속 이력에 있어야 합니다.</li>
          <li><strong>이름</strong>: 영문 이름 토큰 일치(어순·하이픈·중간 이니셜 무시). 영문명이 없으면 한글 성과 이름의 로마자 표기(국어의 로마자 표기법·관용 표기 변형)를 비교합니다.</li>
          <li><strong>주제</strong>: 저자의 상위 주제 중 학과 분야에 해당하는 비율 40% 이상. 생명과학은 OpenAlex 영역(Life Sciences)으로, 나머지 분야는 더 세밀한 OpenAlex 분야 목록(예: 컴퓨터 = Computer Science·Mathematics·Engineering 등)으로 판단해 화학자와 컴퓨터과학자처럼 같은 영역 안의 동명이인을 구분합니다.</li>
          <li><strong>대표 논문</strong>: 교수진 페이지에 실린 논문(최대 8편)을 OpenAlex에서 찾아 실제 저자인지 확인합니다.</li>
          <li><strong>ORCID</strong>: 교수진 페이지에 있으면 최우선으로 사용합니다.</li>
        </ul>
        <p>
          생명과학 학과는 교수마다 OpenAlex 이름 검색으로 후보를 찾습니다. 새로 추가한 학과는 대학의 OpenAlex 저자 명단(최근 소속이 해당 대학이고
          논문 5편 이상인 저자 전체)을 한 번에 받아 그 안에서 이름이 맞는 후보를 찾고, 명단에 없을 때만 이름 검색을 씁니다. 판정 규칙은 같습니다.
          교수진 페이지에 한글 이름만 있는 경우, 대학 명단 안에서 성과 이름의 로마자 표기가 모두 맞고 소속·주제 조건을 만족하는 후보가
          정확히 한 명일 때 신뢰도 “보통”으로 매칭합니다.
        </p>
        <p>
          새로 추가한 학과에서 조건을 만족하는 후보가 여러 명이면 두 가지를 더 봅니다. (1) 같은 ORCID를 가진 프로필들은 동일인의 분할
          프로필로 보고 논문이 많은 쪽을 고릅니다. (2) 연구실을 이끄는 사람은 마지막·교신저자 논문이 많으므로, 분야별 선정 기준에 해당하는
          논문이 기준 이상이면서 다른 후보의 3배 이상인 후보가 한 명뿐이면 그 후보를 고릅니다(같은 이름의 학생·박사후연구원 프로필과 구분).
          같은 프로필에 서로 다른 교수가 매칭되면 둘 다 제외하되, 한쪽만 영문 이름으로 확인된 경우에는 그쪽을 남깁니다.
        </p>
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
          (2)의 사람 검토는 생명과학 연구실에만 했고, 새로 추가한 분야 연구실은 (1)의 소속 필터만 적용되어 있습니다.
        </p>
      </section>

      <section>
        <h2>유사도, 공동연구, 클러스터</h2>
        <ul>
          <li>연구실별로 최근 논문 최대 30편(마지막·교신저자 논문 우선)의 제목과 초록을 <code>allenai-specter</code> 모델로 임베딩하고, 인용 수에 로그 가중치(1 + ln(1 + 인용 수))를 준 평균을 연구실 벡터로 썼습니다.</li>
          <li>
            <strong>연구 주제 유사도 선</strong>: 연구실 벡터의 코사인 유사도에서 각 연구실의 상위 {meta.similarity_k ?? 5}개 이웃 중
            임계값 {meta.similarity_threshold?.toFixed(4) ?? '정보 없음'}(상위 이웃 유사도 분포의 하위 25% 지점)을 넘는 쌍만 남겼습니다.
            여기에 더해 연구실마다 <strong>분야가 다른 연구실 중 가장 가까운 1곳</strong>을 같은 임계값을 넘을 때 이었습니다(학제간 연결).
            분야가 다른 연구실 사이의 선은 “학제간 연결” 보기에서 따로 볼 수 있습니다.
            “연결 이유”는 두 연구실 논문에 공통으로 나타나는 OpenAlex 주제 중 비중이 큰 최대 3개입니다.
          </li>
          <li><strong>공동연구 선</strong>: 지형도 안의 두 PI가 함께 저자로 참여한 논문 수입니다.</li>
          <li>
            <strong>클러스터</strong>: 유사도 이웃 그래프에 Louvain 커뮤니티 탐지(random seed {meta.louvain_seed ?? '정보 없음'})를 적용했고,
            클러스터 수가 연구실 수에 맞는 범위(연구실 106곳일 때 6–12개, 늘어나면 비례해서 증가)가 되는 resolution 중
            {' '}{meta.louvain_resolution ?? '정보 없음'}을 선택해 {clusters.length}개로 나눴습니다. 클러스터는 연구 내용으로만 나누므로 여러 분야가 섞일 수 있습니다.
            라벨은 대표 키워드와 소속 연구실을 보고 직접 붙였습니다.
          </li>
          <li>노드의 처음 위치는 연구실 벡터를 UMAP으로 2차원에 투영한 좌표이며, 같은 클러스터끼리 약하게 모이는 힘을 더했습니다. 노드 색은 학과 분야입니다.</li>
        </ul>
      </section>

      <section>
        <h2>내 후보: 추천과 비교</h2>
        <ul>
          <li><strong>추천</strong>: 담은 연구실 벡터의 평균과 코사인 유사도가 큰 순서입니다. 논문이 섞였거나 매칭이 의심되어 소개를 쓰지 않은 연구실은 벡터를 믿기 어려워 추천하지 않습니다. 벡터는 8비트로 줄여 브라우저에서 계산하며, 담은 목록은 이 브라우저에만 저장되고 서버로 보내지 않습니다. 공유 링크에는 연구실 ID가 들어갑니다.</li>
          <li><strong>찾기</strong>: 뜻을 해석하지 않는 글자 일치 검색입니다. 많은 소개와 키워드, 논문 제목이 각각 한국어와 영어라 언어에 따라 결과가 다를 수 있습니다.</li>
          <li><strong>비교표</strong>: 점수나 순위를 매기지 않습니다. 논문 수는 분야별 관행이 달라 분야가 다르면 직접 비교하기 어렵습니다.</li>
        </ul>
      </section>

      <section>
        <h2>대표 논문 선정 규칙</h2>
        <p>
          PI가 마지막 저자 또는 교신저자이고(수학·컴퓨터는 위의 알파벳 순 규칙으로 인정된 논문 포함) 초록이 있는 논문만 후보로 하며, 연간 인용 수(인용 수 ÷ 출판 후 경과 연수, 최소 1년)로
          정렬해 3편을 고릅니다. 단, 최근 2년 이내 논문을 최소 1편 포함합니다. 후보가 3편보다 적으면 있는 만큼만 표시합니다.
        </p>
      </section>

      <section>
        <h2>요약 작성 방식</h2>
        <p>
          대표 논문의 한국어 요약(한 줄 요약, 연구 배경, 방법, 핵심 발견, 의의)과 연구실 소개는 AI 언어 모델(Anthropic Claude)이
          초록·TLDR·논문 목록만을 근거로 작성했고, 무작위 표본을 원래 초록과 대조해 근거 없는 주장이 없는지 점검했습니다. 초록에서 근거를 찾을 수 없는 항목은 “초록에서 확인 불가”로 두었고, 전문 용어는 처음 나올 때 영문을
          병기했습니다. 저작권을 고려해 <strong>초록 원문은 게재하지 않으며</strong>, 원문은 DOI 링크로 확인할 수 있습니다.
          화학·물리·수학·컴퓨터 연구실과 생명과학 일부의 소개는 <strong>최근 논문 제목과 OpenAlex 키워드만</strong> 근거로 주제 수준에서 썼으며, 표본만 사람이 점검했습니다. 동떨어진 제목은 소개에서 뺐습니다.
        </p>
        {sc && (
          <p className="notice">
            현재 작성 현황: 연구실 {sc.labs}곳 중 <strong>{sc.labs_with_intro}곳</strong>의 소개가 작성되었고,{' '}
            {sc.labs_intro_unavailable > 0 && <><strong>{sc.labs_intro_unavailable}곳</strong>은 논문이 너무 적거나 주제가 동떨어져 쓰지 않고 그 이유를 표시했습니다(동명이인 논문이나 잘못된 매칭이 의심되는 경우 포함). </>}
            대표 논문 요약은 {sc.representative_papers}편 중 <strong>{sc.papers_with_summary}편</strong>이 작성되었고 나머지는 “정보 없음”으로 표시됩니다.
            {gaps.length > 0 && (
              <>
                {' '}<strong>논문 요약의 공백은 특정 분야에 몰려 있습니다</strong>
                {' '}(분야별 미작성: {gaps.map((g) => `${g.label} ${g.missing}/${g.total}편`).join(', ')}).
                요약이 없다고 해서 그 연구실의 연구 성과가 적다는 뜻은 전혀 아니며, 작성 순서 때문입니다.
                비교할 때는 이 점을 감안해 주세요.
              </>
            )}
          </p>
        )}
      </section>

      <section>
        <h2>한계와 면책</h2>
        <ul>
          <li>OpenAlex의 저자 식별과 소속·교신저자 정보에는 오류나 누락이 있을 수 있으며, 그 결과 일부 연구실의 논문 수가 실제와 다르거나 기준에서 빠졌을 수 있습니다.</li>
          <li>최근 5년 논문 기준은 신임 교수나 논문 발표 방식이 다른 분야(학회 발표 중심의 컴퓨터, 저서 중심 분야 등)에 불리할 수 있습니다. 지형도에 없다고 해서 연구 활동이 적다는 뜻은 아닙니다.</li>
          <li>전기전자와 컴퓨터가 합쳐진 학과(GIST 전기전자컴퓨터공학부, DGIST 전기전자컴퓨터공학과)는 공학 계열 확장 때 다루기로 하고 이번 범위에서 뺐습니다. DGIST는 수학 교수 명단이 없습니다.</li>
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
