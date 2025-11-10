/* static/script.js */

/* ====== 로딩 오버레이 ====== */
function showLoading(){const o=document.getElementById("loading-overlay"); if(o) o.style.display="flex";}
function hideLoading(){const o=document.getElementById("loading-overlay"); if(o) o.style.display="none";}

/* ====== 네비게이션 날씨 칩 렌더 ====== */
function renderNavWeather(d){
  const chip = document.getElementById("nav-weather");
  if(!chip) return;
  if (!d || !d.city){
    chip.innerHTML = `<span class="muted">날씨 정보를 불러오지 못했습니다</span>`;
    return;
  }
  chip.innerHTML = `
    <span class="city">${d.city}</span>
    <span>·</span>
    <span>${d.temp}°C</span>
    <span>·</span>
    <span>${d.description}</span>
  `;
}

/* ====== 위치/날씨 ====== */
function getLocation(){
  if(!navigator.geolocation){ alert("이 브라우저에서는 위치 정보를 지원하지 않습니다."); return; }
  navigator.geolocation.getCurrentPosition(sendLocation, showError);
}
function sendLocation(position){
  const lat=position.coords.latitude, lon=position.coords.longitude;
  fetch("/weather",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({lat,lon})})
    .then(r=>r.json())
    .then(d=>{
      // (수정) 페이지별 #weather 대신 항상 상단 칩(#nav-weather) 갱신
      renderNavWeather(d);
    })
    .catch(err=>{
      console.error("에러 발생:", err);
      renderNavWeather(null);
    });
}
function loadNavWeather(){
  if(!navigator.geolocation){ renderNavWeather(null); return; }
  navigator.geolocation.getCurrentPosition((pos)=>{
    const lat=pos.coords.latitude, lon=pos.coords.longitude;
    fetch("/weather",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({lat,lon})
    })
    .then(r=>r.json())
    .then(d=> renderNavWeather(d))
    .catch(()=> renderNavWeather(null));
  }, ()=> renderNavWeather(null));
}
function showError(error){ alert("위치 정보를 가져올 수 없습니다. 오류 코드: "+error.code); }

/* ====== 전역 상태 ====== */
window._recAll = [];   // 전체 추천 (최대 10)
window._recShown = 0;  // 현재 렌더된 개수

// [대화 기록형 추천 결과 누적 구조로 리팩토링]
window._searchHistory = window._searchHistory || [];

function appendRecommendations(query, all) {
  // _searchHistory 배열에 현재 쿼리와 결과를 저장
  window._searchHistory.push({ query, all });

  const container = document.getElementById("results_perfume");
  if (!container) return;

  // recommend-block(1개 검색 결과+유저 입력)을 만들고 하단에 append
  const block = document.createElement("div");
  block.className = "recommend-block";
  block.style.marginBottom = "36px";
  block.innerHTML = `
    <div class="user-bubble" style="margin-bottom:8px;">${query}</div>
    <div class="card-list" id="recList_${window._searchHistory.length}"></div>
    <div style="text-align:center;padding:8px 0;">
      <button class="load-more" id="loadMoreBtn_${window._searchHistory.length}">더보기</button>
    </div>
  `;

  container.appendChild(block);
  
  const list = block.querySelector(`#recList_${window._searchHistory.length}`);
  const btn = block.querySelector(`#loadMoreBtn_${window._searchHistory.length}`);

  let shown = 0;
  function addCards(n) {
    const slice = all.slice(shown, shown + n);
    slice.forEach(p => {
      const brand = p.Brand || p.brand || "Unknown";
      const name = p.Name || p.name || "Untitled";
      const year = (p.Year ?? p.year ?? "") || "";
      const noteRaw = p.Note || p.note || "";
      const notes = parseNotes(noteRaw);
      const popHTML = `
        ${notes.top.length||notes.middle.length||notes.base.length
          ? (noteRows("Top Notes", notes.top) + noteRows("Middle Notes", notes.middle) + noteRows("Base Notes", notes.base))
          : noteRows("Notes", notes.flat)
        }
      `;
      const el = document.createElement("div");
      el.className = "perf-card perf-card--compact";
      el.innerHTML = `
        <div class="perf-title">
          <a href="javascript:void(0)" class="hover-note" data-pop='${encodeURIComponent(popHTML)}'>${brand}</a>
          &nbsp;—&nbsp;
          <a href="javascript:void(0)" class="hover-note" data-pop='${encodeURIComponent(popHTML)}'>${name}</a>
          ${year ? ` <span class="perf-meta">(${year})</span>` : ""}
        </div>
      `;
      el.querySelectorAll(".hover-note").forEach(a => {
        a.addEventListener("mouseenter", ev => {
          const html = decodeURIComponent(a.dataset.pop || "");
          if (html.trim()) showPop(html, ev.clientX, ev.clientY);
        });
        a.addEventListener("mousemove", ev => {
          if (_pop.style.display === "block") showPop(_pop.innerHTML, ev.clientX, ev.clientY);
        });
        a.addEventListener("mouseleave", hidePop);
      });
      list.appendChild(el);
    });
    shown += slice.length;
    if (shown >= all.length) {
      btn.style.display = "none";
    } else {
      btn.style.display = "inline-block";
    }
  }
  addCards(5);
  btn.onclick = () => addCards(5);
}

/* ====== 슬러그 유틸 ====== */
function slugifyNote(n){
  return String(n || "")
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')     // 결합문자 제거
    .replace(/[^a-z0-9]+/g, '-')         // 비영숫자 -> -
    .replace(/^-+|-+$/g,'');             // 앞/뒤 -
}

/* ====== 서버 이미지 URL ====== */
function imgUrlForNote(slug){
  // 서버가 확장자 해결하므로 1회 요청, 404 없음(플레이스홀더로 200 반환)
  return `/note-img/${slug}`;
}

/* ====== 노트 파서: JSON 또는 콤마 텍스트 모두 지원 ====== */
function parseNotes(raw){
  let txt = String(raw ?? "").trim();
  if(!txt) return { top:[], middle:[], base:[], flat:[] };

  // 코드펜스/앞뒤 잡다한 텍스트 제거 후 JSON 블록만 추출
  txt = txt.replace(/```(?:json)?\s*([\s\S]*?)\s*```/ig, "$1");
  const s = txt.indexOf("{"), e = txt.lastIndexOf("}");
  if(s !== -1 && e !== -1 && e > s) txt = txt.slice(s, e+1);

  let obj = null;
  try{
    let norm = txt
      .replace(/(\w+)\s*:/g, '"$1":')
      .replace(/[\u2018\u2019]/g,"'").replace(/[\u201C\u201D]/g,'"')
      .replace(/'/g,'"').replace(/,\s*([}\]])/g, "$1");
    obj = JSON.parse(norm);
  } catch(_){ /* JSON 아님 → 콤마 텍스트 처리 */ }

  if (obj && typeof obj === "object"){
    const top = (obj.top || obj.topNotes || obj.Top || []).map(String);
    const mid = (obj.middle || obj.middleNotes || obj.Heart || obj.Middle || []).map(String);
    const base= (obj.base || obj.baseNotes || obj.Base || []).map(String);

    if(top.length || mid.length || base.length) return { top, middle: mid, base, flat:[] };
    const flat = Object.values(obj).flat().map(String);
    return { top:[], middle:[], base:[], flat };
  }

  const flat = txt.split(/[,/]|·|\|/).map(s=>s.trim()).filter(Boolean);
  return { top:[], middle:[], base:[], flat };
}

/* ====== 팝업 DOM ====== */
const _pop = document.createElement("div");
_pop.className = "note-pop note-pop--plain";  // 라이트 톤 + 가로 레이아웃
document.body.appendChild(_pop);
function hidePop(){ _pop.style.display="none"; }
function showPop(html,x,y){
  _pop.innerHTML = html; _pop.style.display="block";
  const rect=_pop.getBoundingClientRect();
  const px=Math.min(x+16, window.innerWidth-rect.width-8);
  const py=Math.min(y+16, window.innerHeight-rect.height-8);
  _pop.style.left=px+"px"; _pop.style.top=py+"px";
}
document.addEventListener("scroll", hidePop);
document.addEventListener("click", e=>{ if(!_pop.contains(e.target)) hidePop(); });

/* ====== 노트 섹션 HTML (이미지 포함) ====== */
function noteRows(title, arr){
  if(!arr || !arr.length) return "";
  const items = arr.map(n=>{
    const slug = slugifyNote(n);
    const src  = imgUrlForNote(slug);
    return `
      <div class="note-card">
        <img class="note-img" src="${src}" alt="${n}">
        <div class="note-name">${n}</div>
      </div>
    `;
  }).join("");
  return `
    <section class="note-section">
      <h4 class="note-title">${title}</h4>
      <div class="note-line">${items}</div>
    </section>
  `;
}

/* 팝업 전체(섹션들을 세로로 쌓음) — noteRows() 사용으로 수정 */
function buildNotePopup(notes){
  // notes = {top:[], middle:[], base:[]} 형태라고 가정
  return `
    <div class="note-sections">
      ${noteRows("Top Notes", notes.top)}
      ${noteRows("Middle Notes", notes.middle)}
      ${noteRows("Base Notes", notes.base)}
    </div>
  `;
}

/* ====== 추천 카드 렌더링 (브랜드 – 향수명 (연도)만 표시) ====== */
function renderRecommendations(all){
  window._recAll = Array.isArray(all) ? all : [];
  window._recShown = 0;

  const box = document.getElementById("results_perfume");
  if(!box) return;
  box.innerHTML = `
    <div class="card-list" id="recList"></div>
    <div style="text-align:center"><button id="loadMoreBtn" class="load-more">더보기</button></div>
  `;

  const list = document.getElementById("recList");
  const btn  = document.getElementById("loadMoreBtn");

  function addCards(n){
    const slice = window._recAll.slice(window._recShown, window._recShown + n);
    slice.forEach(p=>{
      const brand = p.Brand || p.brand || "Unknown";
      const name  = p.Name  || p.name  || "Untitled";
      const year  = (p.Year ?? p.year ?? "") || "";
      const noteRaw = p.Note || p.note || "";
      const notes = parseNotes(noteRaw);

      // 팝업용 HTML (Top/Middle/Base 또는 단일 Notes)
      const popHTML = `
        ${notes.top.length||notes.middle.length||notes.base.length
          ? (noteRows("Top Notes", notes.top) + noteRows("Middle Notes", notes.middle) + noteRows("Base Notes", notes.base))
          : noteRows("Notes", notes.flat)
        }
      `;

      const el = document.createElement("div");
      el.className = "perf-card perf-card--compact";
      el.innerHTML = `
        <div class="perf-title">
          <a href="javascript:void(0)" class="hover-note" data-pop='${encodeURIComponent(popHTML)}'>${brand}</a>
          &nbsp;—&nbsp;
          <a href="javascript:void(0)" class="hover-note" data-pop='${encodeURIComponent(popHTML)}'>${name}</a>
          ${year ? ` <span class="perf-meta">(${year})</span>` : ""}
        </div>
      `;

      // 호버 → 팝업
      el.querySelectorAll(".hover-note").forEach(a=>{
        a.addEventListener("mouseenter", (ev)=>{
          const html = decodeURIComponent(a.dataset.pop || "");
          if(html.trim()){
            showPop(html, ev.clientX, ev.clientY);
          }
        });
        a.addEventListener("mousemove", (ev)=>{
          if(_pop.style.display==="block"){
            showPop(_pop.innerHTML, ev.clientX, ev.clientY);
          }
        });
        a.addEventListener("mouseleave", hidePop);
      });

      list.appendChild(el);
    });

    window._recShown += slice.length;
    if(window._recShown >= window._recAll.length){
      btn.style.display = "none";
    }else{
      btn.style.display = "inline-block";
    }
  }

  addCards(5);
  btn.onclick = ()=> addCards(5);
}

/* ====== 한 줄 문장 검색 ====== */
async function searchFragranceSentence(){
  const q = (document.getElementById("user_query") || {}).value || "";
  if(!q.trim()){ alert("원하는 향을 문장으로 입력해 주세요."); return; }
  if(!navigator.geolocation){ alert("위치 정보를 지원하지 않습니다."); return; }

  showLoading();
  navigator.geolocation.getCurrentPosition(async pos=>{
    const lat=pos.coords.latitude, lon=pos.coords.longitude;
    try{
      const res = await fetch("/recommend", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ query:q, lat, lon })
      });
      const txt = await res.text();
      const safe = txt.replace(/\bNaN\b/g, "null");
      const data = JSON.parse(safe);

      if(data.error){
        console.error("추천 실패:", data);
        alert("추천 실패: " + (data.detail || data.error));
        return;
      }

      // (수정) 결과 날씨를 상단 칩으로 일관 표기
      const chip = document.getElementById("nav-weather");
      if(chip) chip.textContent = data.weather;

      // 기존 renderRecommendations는 discover.html에서만 appendRecommendations 방식으로 대체!
      // renderRecommendations(data.response || []); // 이 부분은 더 이상 사용되지 않음
      appendRecommendations(q, data.response || []);

      // 필요 시 AI 향수 생성 호출 유지
      const notes = (data.response || []).map(p=>p.Note || p.note);
      generateCustomFragrance(q, q, data.weather_description, notes);
    }catch(err){
      console.error(err);
      alert("추천 요청 중 오류가 발생했습니다.");
    }finally{
      hideLoading();
    }
  }, err=>{ showError(err); hideLoading(); });
}

/* ====== AI 향수 생성 (기존 로직 유지) ====== */
function generateCustomFragrance(user_cat, user_note, weather_desc, notes){
  fetch("/generate-custom-fragrance",{
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body: JSON.stringify({ user_cat, user_note, weather: weather_desc, notes })
  })
  .then(r=>r.json())
  .then(d=>{
    const container=document.getElementById("custom_note_result");
    let raw=(d.generated_note||"").trim();
    raw=raw.replace(/```(?:json)?\s*([\s\S]*?)\s*```/i, "$1").trim();
    const s=raw.indexOf("{"), e=raw.lastIndexOf("}");
    let jc = (s!==-1 && e!==-1) ? raw.slice(s,e+1) : raw;
    jc = jc.replace(/(\w+)\s*:/g,'"$1":').replace(/"\s+/g,'"')
           .replace(/[\u2018\u2019]/g,"'").replace(/[\u201C\u201D]/g,'"')
           .replace(/'/g,'"').replace(/,\s*([}\]])/g,"$1");

    let obj=null;
    try{ obj=JSON.parse(jc); }
    catch(_){ container.innerHTML=`<pre style="white-space:pre-wrap">${raw}</pre>`; return; }

    const safeJoin = a => Array.isArray(a)? a.join(", ") : "";
    container.innerHTML = `
      <div class="ai-card">
        <div class="ai-title">${obj.name || "Untitled"}</div>
        <div class="ai-meta">${obj.category ? `카테고리: ${obj.category}`:""} ${obj.mood? ` · 무드: ${obj.mood}`:""}</div>
        <div class="ai-notes">
          ${obj.top? `<div><strong>Top</strong> — ${safeJoin(obj.top)}</div>`:""}
          ${obj.middle? `<div><strong>Middle</strong> — ${safeJoin(obj.middle)}</div>`:""}
          ${obj.base? `<div><strong>Base</strong> — ${safeJoin(obj.base)}</div>`:""}
        </div>
        ${obj.description? `<p class="ai-desc">${obj.description}</p>`:""}
      </div>
    `;
  })
  .catch(err=>{
    console.error("AI 생성 실패:", err);
    const el=document.getElementById("custom_note_result");
    if(el) el.innerText="AI 생성 중 오류 발생";
  });
}

/* ====== “내 향수” 드롭다운 최근 불러오기 ====== */
function loadMyRecentDropdown(){
  const box = document.getElementById("nav-my-list");
  if(!box) return;
  fetch("/my/recent")
    .then(r=>{
      if(r.status===401){ box.innerHTML=`<li class="muted">로그인이 필요합니다</li>`; return null; }
      return r.json();
    })
    .then(data=>{
      if(!data){ return; }
      const items = Array.isArray(data.items) ? data.items : [];
      if(items.length===0){
        box.innerHTML = `<li class="muted">최근 추천이 없습니다</li>`;
        return;
      }
      box.innerHTML = items.map(rec=>{
        const when = rec.queried_at || "";
        const wc   = rec.weather_desc ? ` · ${rec.weather_desc}` : "";
        const preview = (rec.preview||[]).map(p=>{
          const y = p.year ? ` (${p.year})` : "";
          return `${p.brand||"?"} – ${p.name||"?"}${y}`;
        }).join(", ");
        return `<li>
          <div><strong>${when}</strong>${wc}</div>
          <div class="muted" style="margin-top:2px">${preview||"미리보기 없음"}</div>
        </li>`;
      }).join("");
    })
    .catch(()=>{ box.innerHTML = `<li class="muted">불러오는 중 오류가 발생했습니다</li>`; });
}

/* ====== 드롭다운 열기 토글 ====== */
(function(){
  const dd = document.getElementById("nav-my");
  if(!dd) return;
  const btn = dd.querySelector(".dropdown__toggle");
  if(!btn) return;
  btn.addEventListener("click", ()=>{
    dd.classList.toggle("open");
  });
  document.addEventListener("click",(e)=>{
    if(!dd.contains(e.target)) dd.classList.remove("open");
  });
})();

/* ====== 전역 바인딩 & 초기 로딩 ====== */
window.searchFragranceSentence = searchFragranceSentence;

document.addEventListener("DOMContentLoaded", ()=>{
  const isAuth = (document.body.getAttribute("data-auth")==="1");
  if(isAuth){
    loadMyRecentDropdown();
    loadNavWeather();
  }
});
