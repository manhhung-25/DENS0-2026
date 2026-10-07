/* Research cycles have their own timestamps; they are not video telemetry. */
(() => {
  const q=id=>document.getElementById(id);
  const groups={A_original:'A · Dữ liệu gốc',B_simple:'B · Tăng cường đơn giản',C_physics:'C · Mô phỏng vật lý'};
  let benchmark=null,caseData=null,caseRequest=0,poll=null;
  const number=(x,d=3)=>x==null?'—':Number(x).toFixed(d);
  const stat=x=>`${number(x.mean)} ± ${number(x.std)}`;
  const labels={normal:'Bình thường',bearing:'Ổ bi',friction:'Ma sát',thermal:'Tản nhiệt',backlash:'Độ rơ',slow:'Chậm',sensor_drift:'Trôi cảm biến',encoder_error:'Sai phép đo'};
  function plot(id,series,times,opts={}) {
    const canvas=q(id),{ctx,w,h}=canvasContext(canvas);ctx.clearRect(0,0,w,h);
    if(!times.length||w<80)return;
    const vals=series.flatMap(s=>s.values).filter(Number.isFinite);
    let lo=opts.min??Math.min(...vals),hi=opts.max??Math.max(...vals);
    if(!Number.isFinite(lo)||!Number.isFinite(hi)){lo=0;hi=1}
    if(hi<=lo)hi=lo+1;
    if(opts.threshold!=null){lo=Math.min(lo,opts.threshold);hi=Math.max(hi,opts.threshold)}
    const pad=(hi-lo)*.1;lo-=pad;hi+=pad;
    const left=48,right=12,top=32,bottom=26,W=w-left-right,H=h-top-bottom;
    const duration=times[times.length-1]||1;
    const x=t=>left+W*t/duration,y=v=>top+H*(hi-v)/(hi-lo);
    if(opts.start!=null){ctx.fillStyle='#173c2919';ctx.fillRect(x(opts.start),top,x(opts.end)-x(opts.start),H)}
    ctx.font='12px "Times New Roman",serif';ctx.strokeStyle='#d2dbd1';ctx.fillStyle='#4d5b50';ctx.lineWidth=1;
    for(let k=0;k<4;k++){const yy=top+H*k/3;ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.fillText(number(hi-(hi-lo)*k/3,2),0,yy+4)}
    for(let k=0;k<5;k++)ctx.fillText(number(duration*k/4,1)+'s',x(duration*k/4)-10,h-7);
    series.forEach((s,idx)=>{ctx.beginPath();s.values.forEach((v,i)=>{if(i)ctx.lineTo(x(times[i]),y(v));else ctx.moveTo(x(times[i]),y(v))});ctx.strokeStyle=s.color;ctx.lineWidth=2;ctx.setLineDash(s.dash?[6,4]:[]);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=s.color;ctx.fillText(s.name,48+idx*130,16)});
    if(opts.threshold!=null){ctx.beginPath();ctx.setLineDash([3,3]);ctx.strokeStyle='#774c25';ctx.moveTo(left,y(opts.threshold));ctx.lineTo(w-right,y(opts.threshold));ctx.stroke();ctx.setLineDash([])}
    for(const t of opts.events||[]){ctx.fillStyle='#774c25';ctx.beginPath();ctx.moveTo(x(t),top);ctx.lineTo(x(t)-5,top+9);ctx.lineTo(x(t)+5,top+9);ctx.closePath();ctx.fill()}
    canvas.title=opts.start==null?'Ca bình thường':`Vùng tô: lỗi tiêm ${number(opts.start,2)}–${number(opts.end,2)} s`;
  }
  function bars() {
    const {ctx,w,h}=canvasContext(q('benchmarkChart'));ctx.clearRect(0,0,w,h);
    const left=35,top=28,H=h-65,W=w-left-15;
    ctx.font='12px "Times New Roman",serif';ctx.strokeStyle='#d2dbd1';ctx.fillStyle='#4d5b50';
    for(let i=0;i<5;i++){const y=top+H*i/4;ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(w-15,y);ctx.stroke();ctx.fillText((1-i/4).toFixed(2),0,y+3)}
    Object.entries(benchmark.groups).forEach(([name,result],i)=>{
      const center=left+W*(i+.5)/3,bw=Math.min(35,W/10);
      for(const [key,offset,c] of [['macro_f1',-bw,'#173c29'],['anomaly_pr_auc',2,'#829584']]){
        const value=result[key].mean,x=center+offset;ctx.fillStyle=c;ctx.fillRect(x,top+H*(1-value),bw-2,H*value);
        const std=result[key].std;ctx.strokeStyle='#171d18';ctx.beginPath();ctx.moveTo(x+bw/2,top+H*(1-value-std));ctx.lineTo(x+bw/2,top+H*(1-value+std));ctx.stroke();
      }
      ctx.fillStyle='#171d18';ctx.fillText(name[0],center-3,h-12);
    });
    ctx.fillStyle='#173c29';ctx.fillText('Macro-F1 · đậm',left,16);ctx.fillStyle='#4d5b50';ctx.fillText('PR-AUC · nhạt',left+120,16);
  }
  function matrix() {
    if(!benchmark)return;
    const fold=benchmark.folds.find(f=>String(f.seed)===q('matrixSeed').value)||benchmark.folds[0],group=q('matrixGroup').value;
    const m=fold.groups[group].confusion_matrix;
    q('confusionMatrix').innerHTML=`<table class="research-table"><caption>${esc(groups[group])} · seed ${fold.seed}</caption><thead><tr><th>Thật / dự đoán</th>${benchmark.labels.map(x=>`<th>${esc(labels[x])}</th>`).join('')}</tr></thead><tbody>${m.map((row,i)=>`<tr><th>${esc(labels[benchmark.labels[i]])}</th>${row.map((v,j)=>`<td class="${i===j?'diagonal':''}">${v}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    q('ablationResults').innerHTML=`<table class="research-table"><caption>Seed ${fold.seed} · cùng tập test; mô hình C</caption><thead><tr><th>Nguồn / mô hình</th><th>Macro-F1</th><th>PR-AUC</th><th>Recall sự kiện</th><th>Bỏ sót ca</th><th>Báo giả/giờ</th></tr></thead><tbody>${[['Chỉ rung',fold.ablations.vibration],['Rung + chuyển động',fold.ablations.vibration_pose],['Đa nguồn',fold.groups.C_physics],['Isolation Forest · học bình thường',fold.isolation_forest]].map(([name,r])=>`<tr><th>${esc(name)}</th><td>${number(r.macro_f1)}</td><td>${number(r.anomaly_pr_auc)}</td><td>${number(r.event_recall)}</td><td>${r.missed_fault_cycles}</td><td>${number(r.false_alerts_per_hour,1)}</td></tr>`).join('')}</tbody></table>`;
    drawCase();
  }
  function renderBenchmark(result) {
    benchmark=result;
    q('benchmarkSummary').textContent=`Δ Macro-F1 C−A: ${(result.improvement_macro_f1*100).toFixed(2)} điểm phần trăm. ${result.seeds.length} seed (${result.seeds.join(', ')}). Test đổi tải/tốc độ/nhiễu nhưng dùng cùng phương trình mô phỏng. Chưa có kiểm thử lỗi thật.`;
    q('benchmarkTable').innerHTML=Object.entries(result.groups).map(([k,r])=>`<tr><th>${esc(groups[k])}</th><td>${stat(r.macro_f1)}</td><td>${stat(r.anomaly_pr_auc)}</td><td>${stat(r.event_recall)}</td><td>${stat(r.median_detection_delay_s)}</td><td>${stat(r.false_alerts_per_hour)}</td></tr>`).join('');
    const previous=q('matrixSeed').value;q('matrixSeed').innerHTML=result.seeds.map(s=>`<option>${s}</option>`).join('');if(result.seeds.includes(Number(previous)))q('matrixSeed').value=previous;
    bars();matrix();
  }
  async function cases() {
    const r=await api('/api/research/cases');
    const selected=q('researchCase').value;
    q('researchCase').innerHTML=r.cases.map(c=>`<option value="${esc(c.id)}">${esc(labels[c.label])} · ${esc(c.id)}</option>`).join('');
    if(r.cases.some(c=>c.id===selected))q('researchCase').value=selected;
    if(r.cases.length)await loadCase();
  }
  async function loadCase() {
    const request=++caseRequest,id=q('researchCase').value;
    if(!id)return;
    q('caseMetadata').textContent='Đang tải tín hiệu và kết quả suy luận…';
    try{const result=await api(`/api/research/case/${encodeURIComponent(id)}`);if(request!==caseRequest)return;caseData=result;q('researchJoint').value=result.faulty_joint>=0?result.faulty_joint:0;drawCase()}
    catch(error){q('caseMetadata').textContent=error.message}
  }
  function drawCase() {
    if(!caseData)return;
    const d=caseData,j=Number(q('researchJoint').value),key=q('researchSignal').value;
    const actual=d[key].map(row=>row[j]);const series=[{name:key,color:'#173c29',values:actual}];
    if(['camera','encoder'].includes(key))series.push({name:'lệnh tham chiếu',color:'#171d18',dash:true,values:d.target.map(row=>row[j])});
    const start=d.label==='normal'?null:d.fault_start_s,end=d.fault_end_s;
    plot('caseSignalChart',series,d.t,{start,end});
    const e=d.evaluations[q('matrixGroup').value];
    if(e){plot('caseAlarmChart',[{name:'điểm lỗi',color:'#173c29',values:e.scores}],e.timestamps,{start,end,threshold:e.threshold,events:e.detected_times});q('caseEvents').textContent=`${groups[q('matrixGroup').value]} · Ngưỡng ${number(e.threshold)}. Cảnh báo xác nhận tại: ${e.detected_times.length?e.detected_times.map(t=>number(t,2)+' s').join(', '):'không có'}. Vùng nền là thời gian tiêm lỗi; tam giác là cảnh báo. Kết quả phụ thuộc tín hiệu quan sát.`}
    q('caseMetadata').textContent=`${d.id} · ${labels[d.label]} · ${d.profile} · tải ${number(d.load,2)} · tốc độ ${number(d.speed_hz,2)} Hz · khớp đang xem J${j+1} · khớp tiêm ${d.faulty_joint<0?'không có':'J'+(d.faulty_joint+1)} · kiểm tra số học: ${d.quality.accepted?'đạt':'không đạt'} · dữ liệu mô phỏng.`;
  }
  async function refresh(reloadCases=false) {
    try {
      const result=await api('/api/research');const running=result.job.state==='running';q('runBenchmark').disabled=running;
      q('researchStatus').textContent=running?'Đang chạy ba thí nghiệm A/B/C và đánh giá theo từng nguồn. Kết quả cũ vẫn xem được.':result.job.state==='failed'?`Benchmark lỗi: ${result.job.log}`:result.available?'Kết quả mô phỏng đã sẵn sàng.': 'Chưa có kết quả. Bấm Chạy benchmark hoặc dùng lệnh trong hướng dẫn.';
      if(result.benchmark)renderBenchmark(result.benchmark);
      if(reloadCases||result.job.state==='complete')await cases();
      if(running&&!poll)poll=setInterval(()=>refresh(),4000);
      if(!running&&poll){clearInterval(poll);poll=null}
    } catch(error) {q('researchStatus').textContent=error.message;q('runBenchmark').disabled=false;if(poll){clearInterval(poll);poll=null}}
  }
  q('researchJoint').innerHTML=Array.from({length:7},(_,j)=>`<option value="${j}">J${j+1}</option>`).join('');
  q('researchCase').onchange=loadCase;q('researchJoint').onchange=drawCase;q('researchSignal').onchange=drawCase;q('matrixSeed').onchange=matrix;q('matrixGroup').onchange=matrix;
  q('runBenchmark').onclick=async()=>{q('runBenchmark').disabled=true;try{await jsonPost('/api/research/benchmark',{});await refresh()}catch(error){q('researchStatus').textContent=error.message;q('runBenchmark').disabled=false}};
  window.addEventListener('resize',()=>{if(benchmark)bars();drawCase()});
  refresh(true);
})();
