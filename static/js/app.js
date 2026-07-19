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
      const r=await fetch('/api/metrics',{cache:'no-store'}); if(!r.ok) throw new Error('unit metrics unavailable');
      const d=await r.json();
      set('unit-responses-today',d.summary?.today?.unit_responses ?? '—');
      set('unit-responses-month',d.summary?.month?.unit_responses ?? '—');
      set('unit-responses-ytd',d.summary?.ytd?.unit_responses ?? '—');
      set('chief-responses-ytd',d.summary?.ytd?.chief_responses ?? '—');

      const preferred=['E47','E48','E49','E50','T47','RM49','E650','B47','B48','B49','B50'];
      const byId=new Map((d.units||[]).map(u=>[u.unit_id,u]));
      const grid=document.getElementById('unit-response-grid');
      if(!grid)return;
      grid.innerHTML=preferred.map(id=>{
        const u=byId.get(id)||{unit_id:id,unit_type:id.startsWith('B')?'Chief Officer':id.startsWith('T')?'Truck':id.startsWith('RM')?'Rescue Medic':'Engine',today:0,month:0,ytd:0};
        const label=u.unit_type==='Chief Officer'?'Battalion Chief':u.unit_type;
        return `<article class="unit-response-card ${u.unit_type==='Chief Officer'?'chief-card':''}">
          <div class="unit-card-head"><strong>${u.unit_id}</strong><span>${label}</span></div>
          <div class="unit-periods">
            <div><b>${u.today||0}</b><small>Today</small></div>
            <div><b>${u.month||0}</b><small>Month</small></div>
            <div><b>${u.ytd||0}</b><small>YTD</small></div>
          </div>
        </article>`;
      }).join('');
    }catch(e){
      const grid=document.getElementById('unit-response-grid');
      if(grid)grid.innerHTML='<div class="unit-loading">Unit response data is temporarily unavailable from the public feed.</div>';
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
