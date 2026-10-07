const $ = selector => document.querySelector(selector);
const video = $('#robotVideo');
const color = {real:'#226a44', sim:'#222a23', selected:'#79df91', simOverlay:'#f5fff5', alert:'#194a30', base:'#829584'};
const faultNames = {bearing:'Ổ bi / truyền động',friction:'Ma sát / bôi trơn',thermal:'Suy giảm tản nhiệt',backlash:'Độ rơ / sai tư thế',slow:'Đáp ứng chậm',sensor_drift:'Trôi cảm biến rung',encoder_error:'Sai lệch phép đo vị trí'};
let run = null, selected = 3, selectedJoint = 3, expanded = null, lastDraw = 0, raf = 0, saving = false;

function fmt(t){return `${String(Math.floor(t/60)).padStart(2,'0')}:${(t%60).toFixed(2).padStart(5,'0')}`}
function esc(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function frameIndex(){return Math.min(run.timeline.length-1,Math.max(0,Math.round((video.currentTime||0)*run.fps)))}
function frame(){return run.timeline[frameIndex()]}
async function api(path,options={}){const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw new Error(data.detail||'Lỗi tải dữ liệu');return data}
function jsonPost(path,data){return api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})}
function currentSettings(){return {seed:Number($('#scenarioSeed').value),load:Number($('#scenarioLoad').value),environment:$('#scenarioEnvironment').value}}
function syncSettings(){if(!run)return;$('#scenarioSeed').value=run.seed;$('#scenarioLoad').value=run.load;$('#scenarioEnvironment').value=run.environment;$('#loadText').textContent=`${run.load.toFixed(2)}×`;$('#ensembleLink').href=`/api/ensemble.zip?count=20&seed=${run.seed}`}

async function load(id='default'){
  run=await api(`/api/run/${id}`);
  const pageURL=new URL(window.location.href);if(id==='default')pageURL.searchParams.delete('run');else pageURL.searchParams.set('run',id);history.replaceState(null,'',pageURL);
  $('#csv').href=`/api/run/${id}/export.csv`;
  $('#seek').max=run.duration_s-1/run.fps;
  $('#faultLandmark').innerHTML=run.landmarks.map((name,j)=>`<option value="${j}">${esc(name)}</option>`).join('');
  $('#faultLandmark').value=selected;
  syncSettings();renderLandmarks();renderInjections();renderIncidents();tick(true);
  window.dispatchEvent(new CustomEvent('denso-run-loaded',{detail:run.id}));
}
function renderLandmarks(){
  const row=frame();
  $('#landmarkGrid').innerHTML=run.landmarks.map((name,j)=>{
    const p=row.points[j],parts=name.split(' / ');
    return `<button class="landmark ${selected===j?'active':''}" data-j="${j}" aria-pressed="${selected===j}" aria-label="${esc(name)}"><span class="n">${parts[0]}</span><span class="label">${esc(parts[1]||'')}</span><span class="value">${p?`${Math.round(p[0])}, ${Math.round(p[1])}`:'KHUẤT'}</span></button>`;
  }).join('');
  document.querySelectorAll('.landmark').forEach(button=>button.onclick=()=>{
    selected=Number(button.dataset.j);$('#faultLandmark').value=selected;renderLandmarks();tick(true);
  });
}
function updateLandmarks(row){document.querySelectorAll('.landmark').forEach((button,j)=>{const p=row.points[j];button.querySelector('.value').textContent=p?`${Math.round(p[0])}, ${Math.round(p[1])}`:'KHUẤT'})}

function drawOverlay(row){
  const canvas=$('#poseOverlay'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,840,646);
  const real=row.points[selected],twin=row.twin_points[selected],sig=row.signals[selected];
  if(sig.pose_gap_px>2){
    ctx.save();ctx.setLineDash([7,5]);ctx.strokeStyle=color.simOverlay;ctx.lineWidth=2.5;
    ctx.beginPath();let started=false;
    for(let k=selected;k<7;k++){const p=row.twin_points[k];if(!p){started=false;continue}if(!started){ctx.moveTo(p[0],p[1]);started=true}else ctx.lineTo(p[0],p[1])}
    ctx.strokeStyle='#0b2115';ctx.lineWidth=5;ctx.stroke();ctx.strokeStyle=color.simOverlay;ctx.lineWidth=2.5;ctx.stroke();ctx.setLineDash([]);
    for(let k=selected;k<7;k++){const p=row.twin_points[k],r=row.points[k];if(p&&r&&Math.hypot(p[0]-r[0],p[1]-r[1])>2){ctx.beginPath();ctx.arc(p[0],p[1],5,0,Math.PI*2);ctx.stroke()}}
    if(twin&&real){ctx.beginPath();ctx.moveTo(real[0],real[1]);ctx.lineTo(twin[0],twin[1]);ctx.strokeStyle='#f5fff5aa';ctx.stroke()}
    ctx.restore();
  }
  if(real){ctx.beginPath();ctx.arc(real[0],real[1],11,0,Math.PI*2);ctx.strokeStyle=color.selected;ctx.lineWidth=3;ctx.stroke();ctx.beginPath();ctx.arc(real[0],real[1],2,0,Math.PI*2);ctx.fillStyle=color.selected;ctx.fill()}
}

function canvasContext(canvas){
  const ratio=window.devicePixelRatio||1,w=canvas.clientWidth;
  const h=Number(canvas.dataset.logicalHeight||(canvas.dataset.logicalHeight=canvas.getAttribute('height')));
  if(canvas.width!==Math.round(w*ratio)||canvas.height!==Math.round(h*ratio)){canvas.width=Math.round(w*ratio);canvas.height=Math.round(h*ratio)}
  const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);return {ctx,w,h};
}
function lineChart(id,series,options={}){
  const canvas=document.getElementById(id),{ctx,w,h}=canvasContext(canvas);
  ctx.clearRect(0,0,w,h);const p={l:36,r:10,t:13,b:25},W=w-p.l-p.r,H=h-p.t-p.b;
  if(W<=0||H<=0)return;
  const start=options.start??0,end=options.end??run.duration_s,duration=Math.max(1/run.fps,end-start);
  const xAt=t=>p.l+W*(t-start)/duration;
  const values=series.flatMap(s=>s.values.filter(v=>v!==null&&Number.isFinite(v)));
  let min=options.min??Math.min(...values),max=options.max??Math.max(...values);
  if(!Number.isFinite(min)){min=0;max=1}if(max<=min)max=min+1;
  const gap=(max-min)*.12;min=options.min??(min-gap);max=options.max??max+gap;
  if(options.alerts){for(const incident of options.alerts){const x1=xAt(Math.max(start,incident.start_s)),x2=xAt(Math.min(end,incident.end_s));if(x2<x1)continue;ctx.fillStyle='#226a4420';ctx.fillRect(x1,p.t,Math.max(2,x2-x1),H);ctx.fillStyle=color.alert;ctx.fillRect(x1,p.t,2,6)}}
  ctx.strokeStyle='#dce4db';ctx.lineWidth=1;ctx.font='12px "Times New Roman", serif';ctx.fillStyle='#536358';
  for(let k=0;k<3;k++){const y=p.t+H*k/2;ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.stroke();ctx.fillText((max-(max-min)*k/2).toFixed(options.digits??(max>100?0:1)),2,y+3)}
  for(let k=0;k<5;k++){const x=p.l+W*k/4;ctx.beginPath();ctx.moveTo(x,p.t);ctx.lineTo(x,p.t+H);ctx.stroke();ctx.fillText((start+duration*k/4).toFixed(options.times?1:0)+'s',Math.max(p.l-9,Math.min(w-28,x-8)),h-5)}
  for(const s of series){ctx.beginPath();let started=false;s.values.forEach((v,i)=>{if(v===null||!Number.isFinite(v)){started=false;return}const x=options.times?xAt(options.times[i]):p.l+W*i/(s.values.length-1),y=p.t+H*(max-v)/(max-min);if(!started){ctx.moveTo(x,y);started=true}else ctx.lineTo(x,y)});ctx.strokeStyle=s.color;ctx.lineWidth=s.dash?1.4:2;if(s.dash)ctx.setLineDash([4,4]);ctx.stroke();ctx.setLineDash([])}
  if(options.threshold!=null){const y=p.t+H*(max-options.threshold)/(max-min);ctx.beginPath();ctx.moveTo(p.l,y);ctx.lineTo(w-p.r,y);ctx.setLineDash([3,3]);ctx.strokeStyle='#774c25';ctx.stroke();ctx.setLineDash([])}
  if(options.detected!=null){const x=xAt(options.detected);ctx.beginPath();ctx.moveTo(x,p.t);ctx.lineTo(x,p.t+H);ctx.setLineDash([3,3]);ctx.strokeStyle='#774c25';ctx.stroke();ctx.setLineDash([])}
  const time=video.currentTime||0,cursor=xAt(Math.min(end,time));
  if(time>=start&&time<=end){ctx.beginPath();ctx.moveTo(cursor,p.t);ctx.lineTo(cursor,p.t+H);ctx.strokeStyle='#15281b';ctx.lineWidth=1.2;ctx.stroke();ctx.beginPath();ctx.arc(cursor,p.t+H,3,0,2*Math.PI);ctx.fillStyle='#15281b';ctx.fill()}
  canvas.onclick=event=>{const rect=canvas.getBoundingClientRect();const t=start+(event.clientX-rect.left-p.l)/W*duration;video.currentTime=Math.max(start,Math.min(end,run.duration_s-1/run.fps,t));tick(true)};
  canvas.onkeydown=event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();const t=event.key==='Home'?start:event.key==='End'?end:(video.currentTime||0)+(event.key==='ArrowRight'?1:-1)/run.fps;video.currentTime=Math.max(start,Math.min(end,run.duration_s-1/run.fps,t));tick(true)};
}
function drawTrajectory(){
  const {ctx,w,h}=canvasContext($('#trajectory'));ctx.clearRect(0,0,w,h);const p=20,W=w-40,H=h-40;if(W<=0)return;
  for(let k=0;k<=4;k++){ctx.strokeStyle='#dce4db';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(p+W*k/4,p);ctx.lineTo(p+W*k/4,p+H);ctx.moveTo(p,p+H*k/4);ctx.lineTo(p+W,p+H*k/4);ctx.stroke()}
  for(const kind of ['points','twin_points']){
    ctx.beginPath();let open=false;
    run.timeline.forEach(row=>{const pt=row[kind][selected],real=row.points[selected];if(!pt||kind==='twin_points'&&real&&Math.hypot(pt[0]-real[0],pt[1]-real[1])<2){open=false;return}const x=p+W*pt[0]/840,y=p+H*pt[1]/646;if(!open){ctx.moveTo(x,y);open=true}else ctx.lineTo(x,y)});
    ctx.strokeStyle=kind==='points'?color.real:color.sim;ctx.lineWidth=2;if(kind==='twin_points')ctx.setLineDash([5,4]);ctx.stroke();ctx.setLineDash([]);
  }
  const pt=frame().points[selected];if(pt){ctx.beginPath();ctx.arc(p+W*pt[0]/840,p+H*pt[1]/646,5,0,2*Math.PI);ctx.fillStyle=color.real;ctx.fill()}
}
function drawCharts(){
  const rows=run.timeline,j=selected,col=fn=>rows.map(fn);
  lineChart('speedChart',[{values:col(r=>r.speed_px_s[j]),color:color.real}],{min:0});
  lineChart('distanceChart',[{values:col(r=>r.reference_distance_px),color:color.real}],{min:0});
  lineChart('coverageChart',[{values:col(r=>r.coverage),color:color.real}],{min:0,max:7});
  lineChart('stillChart',[{values:col(r=>r.still_duration_s[j]),color:color.real}],{min:0});
  lineChart('jointChart',[{values:col(r=>r.q_reference_deg[selectedJoint]),color:color.base,dash:true},{values:col(r=>r.q_deg[selectedJoint]),color:color.real}]);
  lineChart('kpErrorChart',[{values:col(r=>r.keypoint_error_px),color:color.real}],{min:0});
  for(const [id,key] of [['sourceVibrationChart','vibration_mm_s'],['sourceSoundChart','sound_dba'],['sourceTemperatureChart','temperature_c'],['sourceCurrentChart','motor_current_a']]){
    lineChart(id,[{values:col(r=>r.source_sim[key]),color:color.sim}]);
  }
  for(const [id,key] of [['vibrationChart','vibration'],['temperatureChart','temperature'],['soundChart','sound']]){
    lineChart(id,[{values:col(r=>r.signals[j].baseline[key]),color:color.base,dash:true},{values:col(r=>r.signals[j][key]),color:color.sim}]);
  }
  lineChart('gapChart',[{values:col(r=>r.signals[j].pose_gap_px),color:color.sim}],{min:0});
  lineChart('delayChart',[{values:col(r=>r.signals[j].cycle_delay_s),color:color.sim}],{min:0});
  lineChart('scoreChart',[{values:col(r=>r.signals[j].score),color:color.alert}],{min:0,max:100,alerts:run.incidents.filter(item=>item.landmark===j)});
  drawTrajectory();
  for(const [id,key] of [['velocityChart','q_velocity_deg_s'],['accelerationChart','q_acceleration_deg_s2'],['jerkChart','q_jerk_deg_s3']])lineChart(id,[{values:col(r=>r[key][selectedJoint]),color:color.real}],{min:Math.min(...col(r=>r[key][selectedJoint]??0))});
  lineChart('regionalCurrentChart',[{values:col(r=>r.signals[j].current),color:color.sim},{values:col(r=>r.signals[j].baseline.current),color:color.base,dash:true}]);
  lineChart('aiCompareChart',[{values:col(r=>r.signals[j].ai_score),color:color.real},{values:col(r=>r.signals[j].rule_score),color:color.sim,dash:true}],{min:0,max:100,alerts:run.injections.filter(x=>x.landmark===j).map(x=>({start_s:x.start_s,end_s:x.start_s+x.duration_s}))});
  lineChart('qualityChart',[{values:col(r=>r.pose_quality),color:color.real},{values:col(r=>r.signals[j].pose_quality),color:color.sim,dash:true}],{min:0,max:1});
  drawIncidentCharts();
}

const incidentChannels=[['vibration','Rung giả lập','mm/s'],['temperature','Nhiệt giả lập','°C'],['sound','Âm giả lập','dB'],['pose_gap_px','Chênh pose what-if','px'],['cycle_delay_s','Trễ ước lượng','s'],['score','Điểm bất thường','/100']];
function incidentChartsMarkup(item){
  const start=Math.max(0,item.start_s-1),end=Math.min(run.duration_s,item.end_s+1);
  return `<section class="incident-evidence" aria-label="Biểu đồ của cảnh báo ${esc(item.id)}"><h3>Biểu đồ bằng chứng · ${esc(run.landmarks[item.landmark].split(' / ')[0])}</h3><p>Phóng đoạn ${start.toFixed(2)}–${end.toFixed(2)} s, có 1 s ngữ cảnh mỗi bên nếu clip còn đủ. Vùng tô là khoảng cảnh báo; vạch nâu đứt là lúc xác nhận ${item.detected_s.toFixed(2)} s. Vạch đen theo video.</p><div class="incident-chart-actions"><button type="button" data-incident-seek="${item.detected_s}">Xem lúc phát hiện</button><button type="button" data-incident-seek="${item.peak_s}">Xem đỉnh bất thường</button></div><div class="incident-chart-grid">${incidentChannels.map(([key,title,unit])=>`<figure><figcaption>${title} <span>(${unit})</span></figcaption><canvas id="incident-${key}" height="150" tabindex="0" aria-label="${title}, ${unit}, từ ${start.toFixed(2)} đến ${end.toFixed(2)} giây. Dùng phím mũi tên để tua video."></canvas></figure>`).join('')}</div><p class="incident-chart-legend">Đường liền: kịch bản; xám đứt: nền mô phỏng ở ba kênh cảm biến. Điểm AI có ngưỡng 50/100, không phải xác suất hỏng. Nhấn biểu đồ hoặc dùng phím mũi tên để tua video. Tín hiệu và tác động lỗi đều là giả lập.</p></section>`;
}
function drawIncidentCharts(){
  const item=run?.incidents.find(x=>x.id===expanded);
  if(!item||!document.getElementById('incident-score'))return;
  const start=Math.max(0,item.start_s-1),end=Math.min(run.duration_s,item.end_s+1);
  const rows=run.timeline.filter(r=>r.t>=start&&r.t<=end),times=rows.map(r=>r.t);
  for(const [key] of incidentChannels){
    const series=[];
    if(['vibration','temperature','sound'].includes(key))series.push({values:rows.map(r=>r.signals[item.landmark].baseline[key]),color:color.base,dash:true});
    series.push({values:rows.map(r=>r.signals[item.landmark][key]),color:key==='score'?color.alert:color.sim});
    const limits=key==='score'?{min:0,max:100,threshold:50}:['pose_gap_px','cycle_delay_s'].includes(key)?{min:0}:{};
    lineChart(`incident-${key}`,series,{...limits,digits:['temperature','cycle_delay_s'].includes(key)?2:1,start,end,times,alerts:[item],detected:item.detected_s});
  }
}
function updateLatent(sig){
  const labels={bearing:'Mòn truyền động',friction:'Ma sát',thermal:'Suy giảm tản nhiệt',backlash:'Độ rơ',slow:'Độ trễ',sensor_drift:'Trôi cảm biến',encoder_error:'Sai lệch đo vị trí'};
  const active=Object.entries(sig.latent);
  $('#latentReadout').innerHTML=`<div class="latent-pill"><span>CHỈ BÁO CHUYỂN ĐỘNG 2D</span><strong>${sig.activity.toFixed(2)}</strong></div><div class="latent-pill"><span>NHIỆT TÍCH LŨY GIẢ LẬP</span><strong>+${sig.thermal_state_c.toFixed(1)} °C</strong></div><div class="latent-pill"><span>SAI KHÁC POSE GIẢ LẬP</span><strong>${sig.pose_gap_px.toFixed(1)} px</strong></div><div class="latent-pill"><span>THAM SỐ LỖI ĐANG BẬT</span><strong>${active.length?active.map(([key,value])=>`${labels[key]} ${value.toFixed(1)}`).join(' · '):'Không có'}</strong></div>`;
}
function tick(force=false){
  if(!run)return;const now=performance.now();if(!force&&now-lastDraw<60)return;lastDraw=now;
  const i=frameIndex(),row=run.timeline[i],point=row.points[selected],sig=row.signals[selected];
  $('#seek').value=Math.min(video.currentTime,Number($('#seek').max));$('#timeText').textContent=`${fmt(video.currentTime||0)} / ${fmt(run.duration_s)}`;
  $('#timeBig').textContent=fmt(video.currentTime||0);$('#frameBig').textContent=`frame ${String(i).padStart(3,'0')} / ${run.timeline.length-1}`;
  $('#playBtn').textContent=video.paused?'▶':'Ⅱ';$('#visibleBadge').textContent=`${row.coverage} / 7 MỐC`;updateLandmarks(row);
  $('#selectedName').textContent=run.landmarks[selected];$('#xyValue').textContent=point?`${point[0].toFixed(0)} / ${point[1].toFixed(0)}`:'Bị che khuất';
  $('#jointValue').textContent=`J${selectedJoint+1} · ${row.q_deg[selectedJoint].toFixed(1)}°`;
  $('#coverageValue').textContent=`${row.coverage} / 7`;$('#sourceValue').textContent=`${row.source_frame} / ${row.cycle}`;
  const show=(id,value,unit,digits=1)=>{const el=$(`#${id}`);if(el)el.textContent=value===null||value===undefined?'—':`${Number(value).toFixed(digits)} ${unit}`};
  show('speedNow',row.speed_px_s[selected],'px/s');show('distanceNow',row.reference_distance_px,'px');
  $('#coverageNow').textContent=`${row.coverage} / 7`;show('stillNow',row.still_duration_s[selected],'s');
  show('jointNow',row.q_deg[selectedJoint],'°');show('kpErrorNow',row.keypoint_error_px,'px');
  show('sourceVibrationNow',row.source_sim.vibration_mm_s,'mm/s');show('sourceSoundNow',row.source_sim.sound_dba,'dBA');
  show('sourceTemperatureNow',row.source_sim.temperature_c,'°C');show('sourceCurrentNow',row.source_sim.motor_current_a,'A',2);
  show('vibrationNow',sig.vibration,'mm/s',2);show('temperatureNow',sig.temperature,'°C');show('soundNow',sig.sound,'dB');
  show('gapNow',sig.pose_gap_px,'px');show('delayNow',sig.cycle_delay_s,'s',2);show('scoreNow',sig.score,'/ 100',0);
  updateLatent(sig);drawOverlay(row);drawCharts();
  show('velocityNow',row.q_velocity_deg_s[selectedJoint],'°/s');show('accelerationNow',row.q_acceleration_deg_s2[selectedJoint],'°/s²');show('jerkNow',row.q_jerk_deg_s3[selectedJoint],'°/s³');
  show('regionalCurrentNow',sig.current,'A',2);$('#aiStateNow').textContent=sig.ai_alarm?'VƯỢT NGƯỠNG':'TRONG NGƯỠNG';show('qualityNow',sig.pose_quality*100,'%',0);$('#phaseNow').textContent=`${row.phase} · ${row.phase_elapsed_s.toFixed(2)} s`;
}
function playbackLoop(){raf=0;tick();if(!video.paused)raf=requestAnimationFrame(playbackLoop)}

function renderInjections(){
  $('#injectionList').innerHTML=run.injections.length?run.injections.map((item,i)=>`<div class="injection-chip">${esc(faultNames[item.fault])} · ${esc(run.landmarks[item.landmark].split(' / ')[0])} · ${item.start_s.toFixed(1)}–${(item.start_s+item.duration_s).toFixed(1)} s <button data-remove="${i}" aria-label="Xóa kịch bản">×</button></div>`).join(''):'<span class="subtle">Không có lỗi tiêm. Đây là ca nền giả lập bình thường.</span>';
  document.querySelectorAll('[data-remove]').forEach(button=>button.onclick=()=>saveRun(run.injections.filter((_,i)=>i!==Number(button.dataset.remove))));
}
function renderIncidents(){
  $('#incidentCount').textContent=run.incidents.length;
  $('#incidentCount').setAttribute('aria-label',`Số cảnh báo: ${run.incidents.length}`);
  $('#incidentList').innerHTML=run.incidents.length?run.incidents.map(item=>{
    const feedback=run.feedback[item.id],e=item.evidence;
    return `<div class="incident ${expanded===item.id?'active':''}"><div class="incident-top"><button data-open="${item.id}" aria-expanded="${expanded===item.id}">${esc(item.label)}<small>${expanded===item.id?'Thu gọn':'Xem biểu đồ & chi tiết'}</small></button><span>SIM · ${item.start_s.toFixed(1)}s</span></div><div class="incident-meta">${esc(run.landmarks[item.landmark])} · ${item.start_s.toFixed(1)}–${item.end_s.toFixed(1)} s · xác nhận tại ${item.detected_s.toFixed(2)} s · ${feedback?'ĐÃ XÁC NHẬN':'CHƯA XÁC NHẬN'}</div>${expanded===item.id?`<div class="incident-body">${incidentChartsMarkup(item)}<strong>Tín hiệu tại đỉnh:</strong> rung ${e.z[0]>=0?'+':''}${e.z[0].toFixed(1)}σ, nhiệt ${e.z[1]>=0?'+':''}${e.z[1].toFixed(1)}σ, âm ${e.z[2]>=0?'+':''}${e.z[2].toFixed(1)}σ; chênh pose mô phỏng ${e.pose_gap_px.toFixed(1)} px; trễ ${e.cycle_delay_s.toFixed(2)} s.<br><strong>Giả thuyết kiểm tra:</strong> ${esc(item.cause)}.<ul>${item.checks.map(check=>`<li>${esc(check)}</li>`).join('')}</ul><form class="feedback-form" data-id="${item.id}"><label>Kết luận<select name="correct"><option value="true" ${feedback?.correct?'selected':''}>Dự đoán đúng</option><option value="false" ${feedback&&!feedback.correct?'selected':''}>Dự đoán sai</option></select></label><label>Kỹ thuật viên<input name="technician" required value="${esc(feedback?.technician||'')}" placeholder="Tên người xác nhận"></label><label>Nguyên nhân thực tế<input name="actual_cause" value="${esc(feedback?.actual_cause||'')}" placeholder="Bắt buộc nếu dự đoán sai"></label><label>Việc đã làm<textarea name="action" required placeholder="Kiểm tra, sửa chữa, đo lại...">${esc(feedback?.action||'')}</textarea></label><button class="primary">Lưu xác nhận</button><span class="feedback-state">${feedback?`Đã lưu: ${feedback.correct?'đúng':'sai'} · ${esc(feedback.created_at)} UTC`:''}</span></form></div>`:''}</div>`;
  }).join(''):'<div class="subtle">Không có cảnh báo. Có thể kịch bản quá nhẹ hoặc tín hiệu đang thiếu hoạt động.</div>';
  document.querySelectorAll('[data-open]').forEach(button=>button.onclick=()=>{
    const item=run.incidents.find(i=>i.id===button.dataset.open);expanded=expanded===item.id?null:item.id;
    selected=item.landmark;$('#faultLandmark').value=selected;video.pause();video.currentTime=item.peak_s;renderLandmarks();renderIncidents();tick(true);
  });
  document.querySelectorAll('[data-incident-seek]').forEach(button=>button.onclick=()=>{video.pause();video.currentTime=Number(button.dataset.incidentSeek);tick(true)});
  document.querySelectorAll('.incident').forEach((element,i)=>{const item=run.incidents[i];if(!item.log_id)return;const link=document.createElement('a');link.href='#history';link.className='incident-log-link';link.textContent='Xem log pose & cảm biến đã lưu';link.onclick=()=>window.dispatchEvent(new CustomEvent('denso-history-open',{detail:item.log_id}));element.querySelector('.incident-meta').after(link)});
  document.querySelectorAll('.feedback-form').forEach(form=>form.onsubmit=async event=>{
    event.preventDefault();const data=Object.fromEntries(new FormData(form));
    try{await jsonPost(`/api/run/${run.id}/incidents/${form.dataset.id}/feedback`,{correct:data.correct==='true',technician:data.technician,actual_cause:data.actual_cause,action:data.action});run=await api(`/api/run/${run.id}`);renderIncidents();window.dispatchEvent(new CustomEvent('denso-feedback-saved'))}catch(error){alert(error.message)}
  });
  drawIncidentCharts();
}
async function saveRun(injections){
  if(saving)return;
  saving=true;
  for(const id of ['addFault','resetFault','clearFault']){$(`#${id}`).disabled=true}
  try{const result=await jsonPost('/api/run',{injections,...currentSettings()});expanded=null;await load(result.id)}catch(error){alert(error.message)}
  finally{saving=false;for(const id of ['addFault','resetFault','clearFault']){$(`#${id}`).disabled=false}}
}
$('#addFault').onclick=()=>saveRun([...run.injections,{fault:$('#faultType').value,landmark:Number($('#faultLandmark').value),start_s:Number($('#faultStart').value),duration_s:Number($('#faultDuration').value),intensity:Number($('#faultIntensity').value),profile:$('#faultProfile').value}]);
$('#resetFault').onclick=()=>saveRun([{fault:'bearing',landmark:3,start_s:5,duration_s:3,intensity:1},{fault:'backlash',landmark:5,start_s:10,duration_s:3,intensity:1}]);
$('#clearFault').onclick=()=>saveRun([]);
$('#faultIntensity').oninput=event=>$('#intensityText').textContent=`${Number(event.target.value).toFixed(1)}×`;
$('#scenarioLoad').oninput=event=>$('#loadText').textContent=`${Number(event.target.value).toFixed(2)}×`;
$('#scenarioSeed').oninput=event=>$('#ensembleLink').href=`/api/ensemble.zip?count=20&seed=${Number(event.target.value)||0}`;
$('#scenarioLoad').onchange=()=>saveRun(run.injections);
$('#scenarioSeed').onchange=()=>saveRun(run.injections);
$('#scenarioEnvironment').onchange=()=>saveRun(run.injections);
$('#jointSelector').innerHTML=Array.from({length:7},(_,j)=>`<option value="${j}">J${j+1}</option>`).join('');$('#jointSelector').value=selectedJoint;$('#jointSelector').onchange=e=>{selectedJoint=Number(e.target.value);tick(true)};
$('#playBtn').onclick=()=>{if(video.paused){if(video.ended)video.currentTime=0;video.play()}else video.pause();tick(true)};
$('#seek').oninput=event=>{video.currentTime=Number(event.target.value);tick(true)};
$('#speed').onchange=event=>video.playbackRate=Number(event.target.value);
video.onplay=()=>{tick(true);if(!raf)raf=requestAnimationFrame(playbackLoop)};
video.onpause=()=>tick(true);video.onseeked=()=>tick(true);video.onended=()=>tick(true);window.onresize=()=>tick(true);
load(new URLSearchParams(window.location.search).get('run')||'default').catch(error=>document.body.insertAdjacentHTML('afterbegin',`<div style="padding:20px;background:#6b2828;color:white">${esc(error.message)}</div>`));
