/* Historical evidence uses its own frame cursor and never changes the live run. */
(() => {
  const q=id=>document.getElementById(id),n=(x,d=2)=>x==null?'—':Number(x).toFixed(d);
  const when=x=>new Intl.DateTimeFormat('vi-VN',{dateStyle:'short',timeStyle:'medium',timeZone:'Asia/Bangkok'}).format(new Date(x));
  let data=null,index=0,offset=0,total=0,currentRun=new URLSearchParams(location.search).get('run')||'default',listRequest=0,detailRequest=0;
  const status=e=>e.correct==null?'Chưa xác nhận':e.correct?'Dự đoán đúng':'Dự đoán sai';
  async function refresh(reset=false){
    if(reset)offset=0;
    const request=++listRequest,params=new URLSearchParams({status:q('historyStatus').value,limit:20,offset});
    if(q('historyScope').value==='current'){
      if(!currentRun){q('historyMessage').textContent='Đang chờ ca hiện tại lưu dữ liệu…';return}
      params.set('run_id',currentRun);
    }
    q('historyMessage').textContent='Đang đọc lịch sử đã lưu…';
    try{
      const r=await api('/api/history?'+params);if(request!==listRequest)return;
      total=r.total;
      q('historyRows').innerHTML=r.events.map(e=>`<tr><th>${esc(e.incident_id)}<small>${esc(e.run_id)}</small></th><td>${esc(e.label)}</td><td>${esc(['L0','L2','L3','L4','L6','L7','EE'][e.landmark])}</td><td>${n(e.start_s)}–${n(e.end_s)}<small>xác nhận ${n(e.detected_s)}</small></td><td>${n(e.score,0)}/100</td><td>${esc(when(e.saved_at_utc))}</td><td>${status(e)}</td><td><button type="button" class="secondary" data-history-open="${esc(e.id)}">Xem log</button></td></tr>`).join('');
      q('historyMessage').textContent=total?`${total} sự kiện đã lưu. Mỗi log gồm pose toàn cánh tay, cảm biến ở 7 vùng và góc J1–J7 trước–trong–sau cảnh báo.`:'Chưa có sự kiện trong bộ lọc. Ca bình thường không tạo log bất thường; các ca cũ được lưu khi mở lại.';
      q('historyPage').textContent=`Trang ${Math.floor(offset/20)+1} / ${Math.max(1,Math.ceil(total/20))}`;
      q('historyPrev').disabled=offset===0;q('historyNext').disabled=offset+20>=total;
      document.querySelectorAll('[data-history-open]').forEach(b=>b.onclick=()=>open(b.dataset.historyOpen));
    }catch(e){if(request===listRequest)q('historyMessage').textContent=e.message}
  }
  async function open(id){
    const request=++detailRequest;q('historyMessage').textContent='Đang đọc bản chụp bằng chứng…';
    try{
      const r=await api('/api/history/'+encodeURIComponent(id));if(request!==detailRequest)return;
      data=r;index=r.timeline.reduce((best,row,i)=>Math.abs(row.t-r.incident.peak_s)<Math.abs(r.timeline[best].t-r.incident.peak_s)?i:best,0);
      q('historyDetail').hidden=false;
      q('historyEventTitle').textContent=`${r.incident.label} · ${r.incident.id} · ca ${r.run_id}`;
      q('historyEventMeta').textContent=`Lưu ${when(r.saved_at_utc)} (UTC+7) · ${r.window.frame_count} frame · đoạn ${n(r.window.start_s)}–${n(r.window.end_s)} s · xác nhận ${n(r.incident.detected_s)} s. SHA-256 bản chụp: ${r.evidence_archive.sha256}`;
      q('historyLandmark').innerHTML=r.landmarks.map((s,j)=>`<option value="${j}">${esc(s)}</option>`).join('');q('historyLandmark').value=r.incident.landmark;
      q('historyJSON').href=`/api/history/${encodeURIComponent(id)}/export.json`;q('historyCSV').href=`/api/history/${encodeURIComponent(id)}/export.csv`;
      q('historyRun').href=`/?run=${encodeURIComponent(r.run_id)}#maintenance`;
      q('historyFrame').max=r.timeline.length-1;
      q('historyFeedback').innerHTML=r.maintenance_history.length?r.maintenance_history.map(a=>`<p><strong>${esc(when(a.saved_at_utc))} UTC+7 · ${esc(a.feedback.technician)}</strong><br>${a.feedback.correct?'Dự đoán đúng':'Dự đoán sai'} · ${esc(a.feedback.actual_cause||'Chưa ghi nguyên nhân')}<br>${esc(a.feedback.action)}</p>`).join(''):'<p>Chưa có kết luận của kỹ thuật viên. Xác nhận trong mục Bảo trì của ca tương ứng.</p>';
      q('historyMessage').textContent='Đang xem bằng chứng cố định trong SQLite; không tính lại mô hình.';
      render();
      q('historyDetail').scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
    }catch(e){if(request===detailRequest)q('historyMessage').textContent=e.message}
  }
  function chart(id,key,isScore=false){
    const {ctx,w,h}=canvasContext(q(id));ctx.clearRect(0,0,w,h);if(!data||w<80)return;
    const rows=data.timeline,j=Number(q('historyLandmark').value),times=rows.map(r=>r.t),start=times[0],end=times.at(-1),span=Math.max(end-start,1/data.fps);
    const series=[{values:rows.map(r=>r.signals[j][key]),color:'#173c29'}];
    if(['vibration','temperature','sound','current'].includes(key))series.unshift({values:rows.map(r=>r.signals[j].baseline[key]),color:'#829584',dash:true});
    const values=series.flatMap(s=>s.values).filter(Number.isFinite);let lo=isScore?0:Math.min(...values),hi=isScore?100:Math.max(...values);
    if(hi<=lo)hi=lo+1;if(!isScore){const p=(hi-lo)*.1;lo-=p;hi+=p}
    const left=42,top=22,right=10,bottom=28,W=w-left-right,H=h-top-bottom,x=t=>left+W*(t-start)/span,y=v=>top+H*(hi-v)/(hi-lo);
    ctx.fillStyle='#226a4420';ctx.fillRect(x(data.incident.start_s),top,Math.max(2,x(data.incident.end_s)-x(data.incident.start_s)),H);
    ctx.font='12px "Times New Roman",serif';ctx.fillStyle='#536358';ctx.strokeStyle='#dce4db';ctx.lineWidth=1;
    for(let k=0;k<3;k++){const yy=top+H*k/2;ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.fillText(n(hi-(hi-lo)*k/2,key==='temperature'?2:1),0,yy+3)}
    for(let k=0;k<5;k++)ctx.fillText(n(start+span*k/4,1)+'s',Math.min(w-30,x(start+span*k/4)-10),h-7);
    for(const s of series){ctx.beginPath();s.values.forEach((v,i)=>{if(i)ctx.lineTo(x(times[i]),y(v));else ctx.moveTo(x(times[i]),y(v))});ctx.lineWidth=2;ctx.strokeStyle=s.color;ctx.setLineDash(s.dash?[4,4]:[]);ctx.stroke();ctx.setLineDash([])}
    ctx.strokeStyle='#774c25';ctx.setLineDash([3,3]);ctx.beginPath();ctx.moveTo(x(data.incident.detected_s),top);ctx.lineTo(x(data.incident.detected_s),top+H);ctx.stroke();
    if(isScore){ctx.beginPath();ctx.moveTo(left,y(50));ctx.lineTo(w-right,y(50));ctx.stroke()}
    ctx.setLineDash([]);ctx.strokeStyle='#15281b';ctx.beginPath();ctx.moveTo(x(rows[index].t),top);ctx.lineTo(x(rows[index].t),top+H);ctx.stroke();
    ctx.fillStyle='#173c29';ctx.fillText(isScore?'Điểm AI đã lưu':q('historySignal').selectedOptions[0].textContent,left,13);
    q(id).onclick=e=>{const rect=q(id).getBoundingClientRect(),t=start+(e.clientX-rect.left-left)/W*span;index=rows.reduce((b,r,i)=>Math.abs(r.t-t)<Math.abs(rows[b].t-t)?i:b,0);render()};
    q(id).onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();index=e.key==='Home'?0:e.key==='End'?rows.length-1:Math.max(0,Math.min(rows.length-1,index+(e.key==='ArrowRight'?1:-1)));render()};
  }
  function pose(row){
    const canvas=q('historyPose'),ctx=canvas.getContext('2d');ctx.clearRect(0,0,840,646);ctx.fillStyle='#f5f8f2';ctx.fillRect(0,0,840,646);
    ctx.font='18px "Times New Roman",serif';
    for(const [key,color,dashed] of [['points','#226a44',false],['twin_points','#222a23',true]]){
      ctx.beginPath();let begun=false;row[key].forEach(p=>{if(!p){begun=false;return}if(!begun){ctx.moveTo(...p);begun=true}else ctx.lineTo(...p)});
      ctx.strokeStyle=color;ctx.lineWidth=3;ctx.setLineDash(dashed?[8,6]:[]);ctx.stroke();ctx.setLineDash([]);
      if(!dashed)row[key].forEach((p,j)=>{if(!p)return;ctx.beginPath();ctx.arc(...p,6,0,Math.PI*2);ctx.fillStyle=color;ctx.fill();ctx.fillText(data.landmarks[j].split(' / ')[0],p[0]+10,Math.max(20,p[1]-8))});
    }
  }
  function render(){
    if(!data)return;
    const row=data.timeline[index],j=Number(q('historyLandmark').value),joint=Number(q('historyJoint').value),sig=row.signals[j];
    const phase=row.t<data.incident.start_s?'TRƯỚC CẢNH BÁO':row.t>data.incident.end_s?'SAU CẢNH BÁO':'TRONG CẢNH BÁO';
    q('historyFrame').value=index;q('historyFrameTime').textContent=`${n(row.t)} s · frame video ${Math.round(row.t*data.fps)} · ${phase}`;
    q('historyPoseCaption').textContent=`Tất cả 7 mốc · ${n(row.t)} s · ảnh DREAM ${row.source_frame} · HoRoPose đã lưu`;
    q('historyReadout').innerHTML=`<h4>Giá trị tại frame đang xem</h4><p><strong>${esc(data.landmarks[j])}</strong></p><p>Rung ${n(sig.vibration)} mm/s · nhiệt ${n(sig.temperature)} °C<br>Âm ${n(sig.sound)} dB · dòng ${n(sig.current)} A</p><p>Chênh pose ${n(sig.pose_gap_px)} px · trễ ${n(sig.cycle_delay_s)} s<br>AI ${n(sig.score,0)}/100 · độ phủ what-if ${n(sig.pose_quality*100,0)}%</p><p>Khớp chọn độc lập: <strong>J${joint+1} · ${n(row.q_deg[joint])}°</strong><br>Vận tốc ${n(row.q_velocity_deg_s[joint])} °/s · jerk ${n(row.q_jerk_deg_s3[joint])} °/s³</p><p>Model ${esc(data.method.version)} · seed ${data.context.seed} · tải ${n(data.context.load)}×<br>Cảm biến giả lập; góc khớp là dự đoán HoRoPose.</p>`;
    q('historyPoseRows').innerHTML=data.landmarks.map((name,k)=>{const p=row.points[k],t=row.twin_points[k],s=row.signals[k];return `<tr><th>${esc(name)}</th><td>${n(p?.[0])}</td><td>${n(p?.[1])}</td><td>${n(t?.[0])}</td><td>${n(t?.[1])}</td><td>${n(s.vibration)}</td><td>${n(s.temperature)}</td><td>${n(s.sound)}</td><td>${n(s.current)}</td><td>${n(s.score,0)}</td></tr>`}).join('');
    q('historyJointRows').innerHTML=row.q_deg.map((v,k)=>`<tr><th>J${k+1}</th><td>${n(v)}</td><td>${n(row.q_velocity_deg_s[k])}</td><td>${n(row.q_acceleration_deg_s2[k])}</td><td>${n(row.q_jerk_deg_s3[k])}</td></tr>`).join('');
    pose(row);chart('historySignalChart',q('historySignal').value);chart('historyScoreChart','score',true);
  }
  q('historyJoint').innerHTML=Array.from({length:7},(_,j)=>`<option value="${j}">J${j+1}</option>`).join('');q('historyJoint').value=3;
  q('historyRefresh').onclick=()=>refresh();q('historyScope').onchange=()=>refresh(true);q('historyStatus').onchange=()=>refresh(true);
  q('historyPrev').onclick=()=>{offset=Math.max(0,offset-20);refresh()};q('historyNext').onclick=()=>{offset+=20;refresh()};
  q('historyLandmark').onchange=render;q('historyJoint').onchange=render;q('historySignal').onchange=render;
  q('historyFrame').oninput=e=>{index=Number(e.target.value);render()};
  window.addEventListener('resize',render);
  window.addEventListener('denso-run-loaded',e=>{currentRun=e.detail;refresh(true)});
  window.addEventListener('denso-history-open',e=>open(e.detail));
  window.addEventListener('denso-feedback-saved',()=>{refresh();if(data)open(data.id)});
  refresh();
})();
