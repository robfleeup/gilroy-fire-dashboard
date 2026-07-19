(() => {
  const slides=[...document.querySelectorAll(".hero-slide")], dots=[...document.querySelectorAll(".slide-dot")];
  let current=0,timer;
  const show=i=>{current=(i+slides.length)%slides.length;slides.forEach((s,n)=>s.classList.toggle("is-active",n===current));dots.forEach((d,n)=>d.classList.toggle("is-active",n===current));};
  const rotate=()=>{clearInterval(timer);timer=setInterval(()=>show(current+1),6500);};
  dots.forEach((d,i)=>d.addEventListener("click",()=>{show(i);rotate();})); show(0); rotate();

  const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
  async function refreshOperations(){
    try{
      await fetch('/api/sync',{method:'POST'}).catch(()=>null);
      const r=await fetch('/api/current-operations',{cache:'no-store'}); if(!r.ok) throw new Error('feed unavailable');
      const d=await r.json();
      set('active-incidents',d.active_incidents); set('incidents-today',d.incidents_today); set('ems-today',d.ems_today);
      set('fire-today',d.fire_other_today); set('units-assigned',d.gilroy_units_committed); set('chiefs-assigned',d.chiefs_committed);
      set('als-assigned',d.als_assigned); set('bls-assigned',d.bls_assigned);
      const updated=new Date(d.updated_at); set('live-update-status','Updated '+updated.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'})+' • OurGilroy public incident feed');
      await refreshUnitResponses();
    }catch(e){ set('live-update-status','Live feed temporarily unavailable — verified historical data remains displayed'); }
  }

  async function refreshUnitResponses(){
    try{
      const r=await fetch('/static/data/unit_workload_2026.json',{cache:'no-store'}); if(!r.ok) throw new Error('Unit workload snapshot unavailable');
      const d=await r.json();
      set('workload-incidents',(d.incident_records_90_day||0).toLocaleString());
      set('workload-unit-responses',(d.gilroy_unit_responses_90_day||0).toLocaleString());
      set('workload-average',Number(d.average_gilroy_units_per_incident||0).toFixed(2));
      const units=d.units||{};
      const preferred=['E48','E47','E49','RM49','B47','B48','B49','E650','T47','E50','B50','E348'];
      const grid=document.getElementById('unit-response-grid'); if(!grid)return;
      grid.innerHTML=preferred.map(id=>{
        const u=units[id]||{last_90_days:0,ytd:0};
        const label=id.startsWith('B')?'Chief Officer':id.startsWith('T')?'Truck':id.startsWith('RM')?'Rescue Medic':id==='E650'?'Support Engine':id==='E348'?'Reserve Engine':'Engine';
        return `<article class="unit-response-card ${id.startsWith('B')?'chief-card':''}">
          <div class="unit-card-head"><strong>${id}</strong><span>${label}</span></div>
          <div class="unit-periods two-periods">
            <div><b>${(u.last_90_days||0).toLocaleString()}</b><small>Last 90 Days</small></div>
            <div><b>${(u.ytd||0).toLocaleString()}</b><small>2026 YTD</small></div>
          </div>
        </article>`;
      }).join('');
    }catch(e){
      const grid=document.getElementById('unit-response-grid');
      if(grid)grid.innerHTML='<div class="unit-loading">Verified unit response activity could not be loaded.</div>';
    }
  }
  async function refreshWeather(){
    try{
      const [wr,ar]=await Promise.all([fetch('/api/weather'),fetch('/api/alerts')]); const w=await wr.json(),a=await ar.json();
      if(w.error) throw new Error(w.error);
      const parts=[]; if(w.temperature_f!=null)parts.push(w.temperature_f+'°F'); if(w.humidity!=null)parts.push('RH '+w.humidity+'%'); if(w.wind_mph!=null)parts.push('Wind '+w.wind_mph+' mph');
      set('weather-summary',parts.join(' • ')||w.description||'Current conditions');
      set('weather-detail',a.count? a.alerts[0].event+' active for the Gilroy area' : (w.description||'No active NWS alert shown'));
    }catch(e){set('weather-summary','Current conditions available from NWS');set('weather-detail','Open the National Weather Service for current Gilroy conditions');}
  }
  async function refreshVegetation(){try{const r=await fetch('/api/vegetation-activity');const d=await r.json();set('veg-count',d.count+' incidents in 15 days');set('veg-detail',d.average_per_day+' per day • most recent '+d.most_recent);}catch(e){}}
  refreshOperations(); refreshWeather(); refreshVegetation(); setInterval(refreshOperations,180000); setInterval(refreshWeather,900000);
})();
