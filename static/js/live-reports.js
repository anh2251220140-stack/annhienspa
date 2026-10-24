(async () => {
  const {api,escape:e,money}=window.spaLive, $=s=>document.querySelector(s);
  const labels={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',completed:'Đã hoàn thành',cancelled:'Đã hủy'};
  const noData='<p class="admin-analytics-no-data">Chưa có dữ liệu phù hợp trong kỳ.</p>';
  const stats=rows=>rows.map(([label,value,caption],i)=>`<article class="admin-finance-stat ${i?'':'is-featured'}"><div class="admin-finance-stat-heading"><span>${e(label)}</span>${window.spaIcon('note')}</div><strong>${e(value)}</strong><p>${e(caption)}</p></article>`).join('');
  const bars=rows=>{const max=Math.max(1,...rows.map(r=>Number(r.value)));return rows.length?rows.map(r=>`<div class="admin-analytics-bar is-${r.tone||'neutral'}" tabindex="0" title="${e(r.label)}: ${r.value}"><div><span>${e(r.label)}</span><strong>${r.value}</strong></div><div class="admin-analytics-track"><span style="width:${Number(r.value)/max*100}%"></span></div></div>`).join(''):noData;};
  function reset(){const today=new Date().toLocaleDateString('sv-SE',{timeZone:'Asia/Ho_Chi_Minh'});$('#report-from').value=today.slice(0,8)+'01';$('#report-to').value=today;}
  async function render(){
    const error=$('#report-filter-error');
    try{
      const d=await api('/api/dashboard/?'+new URLSearchParams({start:$('#report-from').value,end:$('#report-to').value,status:$('#report-status-filter').value}));
      error.hidden=true;$('#report-period').textContent=`Kỳ: ${d.start} — ${d.end}. Doanh thu theo ngày thanh toán; lịch hẹn theo ngày hẹn.`;
      const active=d.statuses.filter(s=>s.status!=='cancelled').reduce((sum,s)=>sum+s.count,0),completed=d.statuses.find(s=>s.status==='completed')?.count||0;
      $('#report-stats').innerHTML=stats([['Doanh thu đã thanh toán',money(d.revenue),'Theo ngày thanh toán'],['Lịch hẹn',d.appointments,'Theo ngày hẹn và trạng thái đã chọn'],['Lượt đặt không hủy',active,'Dữ liệu lịch hẹn'],['Điểm trải nghiệm',d.reviewCount?Number(d.rating).toFixed(1)+' / 5':'—',`${d.reviewCount} đánh giá trong kỳ`]]);
      $('#report-empty').hidden=!!(d.appointments||Number(d.revenue)||d.reviewCount);
      const max=Math.max(1,...d.daily.map(x=>Number(x.total)));
      $('#report-revenue').innerHTML=d.daily.length?`<div class="admin-revenue-days">${d.daily.map(x=>`<div class="admin-revenue-day" tabindex="0" aria-label="${x.day}: ${money(x.total)}"><div class="admin-revenue-day-label"><span>${x.day}</span><strong>${money(x.total)}</strong></div><div class="admin-analytics-track"><span style="width:${Number(x.total)/max*100}%"></span></div></div>`).join('')}</div>`:noData;
      $('#report-status').innerHTML=bars(d.statuses.map(x=>({label:labels[x.status],value:x.count,tone:x.status})));
      $('#report-services').innerHTML=bars(d.popular.map(x=>({label:x.service__name,value:x.count,tone:'positive'})));
      $('#report-ratings').innerHTML=bars(d.ratings.map(x=>({label:`${x.rating} sao`,value:x.count})));
      $('#report-rows').innerHTML=d.report.filter(x=>x.appointments||Number(x.revenue)||x.reviews).map(x=>`<tr><td>${e(x.service)}</td><td>${x.appointments}</td><td>${x.active}</td><td>${x.completed}</td><td>${money(x.revenue)}</td><td>${x.reviews}</td><td>${x.reviews?Number(x.rating).toFixed(1):'—'}</td></tr>`).join('')||'<tr><td colspan="7">Không có dữ liệu trong kỳ.</td></tr>';
      $('#report-total').innerHTML=`<tr><th>Tổng trong kỳ</th><td>${d.appointments}</td><td>${active}</td><td>${completed}</td><td>${money(d.revenue)}</td><td>${d.reviewCount}</td><td>${d.reviewCount?Number(d.rating).toFixed(1):'—'}</td></tr>`;
      $('#report-insights').innerHTML=`<article><p>Doanh thu đã nhận: <strong>${money(d.revenue)}</strong></p></article><article><p><strong>${completed}</strong> lịch đã hoàn thành trong kỳ.</p></article><article><p><strong>${d.reviewCount}</strong> đánh giá trong kỳ.</p></article>`;
    }catch(ex){error.hidden=false;error.textContent=ex.message;}
  }
  $('#report-filters').addEventListener('submit',event=>{event.preventDefault();render();});
  $('#report-reset').onclick=()=>{reset();$('#report-status-filter').value='';render();}; reset();await render();
})();
