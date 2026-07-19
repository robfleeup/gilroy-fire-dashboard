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
    }catch(e){ set('live-update-status','Live feed temporarily unavailable — verified historical data remains displayed'); }
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
