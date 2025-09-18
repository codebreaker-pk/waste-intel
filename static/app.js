(function(){
  const $ = (sel, el=document)=> el.querySelector(sel);
  const $$ = (sel, el=document)=> el.querySelectorAll(sel);

  // theme toggle
  const root = document.documentElement;
  const saved = localStorage.getItem("theme") || "light";
  root.setAttribute("data-theme", saved);
  $("#themeToggle")?.addEventListener("click", ()=>{
    const cur = root.getAttribute("data-theme")==="dark" ? "light" : "dark";
    root.setAttribute("data-theme", cur);
    localStorage.setItem("theme", cur);
  });

  // live prediction
  const form = $("#predictForm");
  const results = $("#resultsCard");
  const predVal = $("#predVal");
  const gauge = $("#gauge");
  const predBadge = $("#predBadge");
  const chips = $("#chips");
  const cmpBody = $("#cmpBody");
  let cmpChart;

  function formDataObj() {
    const data = {};
    new FormData(form).forEach((v,k)=> data[k]=v);
    // cast numbers
    ["year","waste_gen","pop_density","eff_score","cost","campaigns","capacity"].forEach(k=>{
      data[k] = Number(data[k]);
    });
    return data;
  }

  function badgeClass(b){ // success/warning/danger
    return `badge bg-${b} px-3 py-2`;
  }

  function updateUI(json, inputs){
    results.classList.remove("d-none");
    predVal.textContent = `${json.prediction}%`;
    gauge.style.setProperty("--p", json.prediction);
    predBadge.className = badgeClass(json.badge);
    predBadge.textContent = json.label;

    // chips
    chips.innerHTML = `
      <span class="chip"><i class="bi bi-geo"></i> ${inputs.city}</span>
      <span class="chip"><i class="bi bi-recycle"></i> ${inputs.waste_type}</span>
      <span class="chip"><i class="bi bi-trash3"></i> ${inputs.method}</span>
      <span class="chip"><i class="bi bi-people"></i> ${json.density_bin}</span>
    `;

    // table
    const base = json.prediction;
    cmpBody.innerHTML = "";
    Object.entries(json.compare).forEach(([m,val])=>{
      const delta = (val - base).toFixed(1);
      const deltaHTML = delta>0 ? `<span class="text-success">+${delta}</span>` :
                        (delta<0 ? `<span class="text-danger">${delta}</span>` : `<span class="text-muted">0.0</span>`);
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${m}</td>
        <td>
          <div class="bar bg-light"><div class="bar-fill" style="width:${val}%"></div></div>
          <span class="text-muted">${val}%</span>
        </td>
        <td>${deltaHTML}</td>
      `;
      cmpBody.appendChild(row);
    });

    // chart
    const ctx = $("#cmpChart").getContext("2d");
    if (cmpChart) cmpChart.destroy();
    cmpChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: Object.keys(json.compare),
        datasets: [{ label: 'Predicted %', data: Object.values(json.compare) }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { y: { suggestedMin: 0, suggestedMax: 100 } }
      }
    });
  }

  async function callAPI(){
    const payload = formDataObj();
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const json = await res.json();
    updateUI(json, payload);
  }

  // submit (no reload)
  form?.addEventListener("submit", (e)=>{
    e.preventDefault();
    callAPI();
  });

  // live mode toggle (debounced input -> API)
  let live = false, t=null;
  const liveBtn = $("#liveBtn");
  liveBtn?.addEventListener("click", ()=>{
    live = !live;
    liveBtn.classList.toggle("btn-outline-primary");
    liveBtn.classList.toggle("btn-success");
    liveBtn.innerHTML = live ? '<i class="bi bi-broadcast-pin"></i> Live ON' : '<i class="bi bi-broadcast"></i> Live update';
  });
  $$(".live").forEach(inp=>{
    inp.addEventListener("input", ()=>{
      if (!live) return;
      clearTimeout(t);
      t = setTimeout(callAPI, 250);
    });
    inp.addEventListener("change", ()=>{
      if (!live) return;
      clearTimeout(t);
      t = setTimeout(callAPI, 50);
    });
  });
})();
