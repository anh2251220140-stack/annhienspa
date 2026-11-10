/* Reports presentation only; calculation and access rules remain in the API. */
(async () => {
  'use strict';
  const root=document.querySelector('[data-live-reports]');if(!root)return;
  const {api,escape:esc,money}=window.spaLive,$=s=>root.querySelector(s),icon=n=>window.spaIcon(n==='wallet'?'note':n);
  const labels={pending:'Chờ xác nhận',confirmed:'Đã xác nhận',completed:'Đã hoàn thành',cancelled:'Đã hủy'};
  let revision=0,busy=false,serverToday='',lastRequest=null;
  const dateLabel=iso=>iso?iso.split('-').reverse().join('/'):'—';
  function parseDisplay(value){
    const m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value||'');if(!m)return null;
    const iso=`${m[3]}-${m[2]}-${m[1]}`,d=new Date(iso+'T00:00:00Z');
    return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===iso?iso:null;
  }
  function setDay(side,iso){$('#report-'+side).value=iso;$('#report-'+side+'-display').value=dateLabel(iso);}
  function currentMonth(){
    const today=serverToday||new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
    setDay('from',today.slice(0,8)+'01');setDay('to',today);$('#report-status-filter').value='';
  }
  function getFilters(){
    const start=parseDisplay($('#report-from-display').value),end=parseDisplay($('#report-to-display').value);
    $('#report-from-display').setAttribute('aria-invalid',String(!start));$('#report-to-display').setAttribute('aria-invalid',String(!end));
    if(!start||!end)throw Error('Nhập ngày hợp lệ theo dd/mm/yyyy.');
    if(start>end||(Date.parse(end)-Date.parse(start))/86400000>3660)throw Error('Chọn khoảng ngày hợp lệ, tối đa 10 năm.');
    $('#report-from').value=start;$('#report-to').value=end;
    return {start,end,status:$('#report-status-filter').value};
  }
  function controls(){for(const el of $('#report-filters').querySelectorAll('input,select,button'))el.disabled=busy;$('#report-retry').disabled=busy;root.setAttribute('aria-busy',String(busy));}
  const empty=(message,symbol)=>`<div class="report-chart-empty">${icon(symbol)}<p>${esc(message)}</p></div>`;
  function bars(rows){
    const maximum=Math.max(1,...rows.map(r=>Number(r.value)));
    return rows.map(r=>`<div class="admin-analytics-bar is-${r.tone||'neutral'}" tabindex="0" aria-label="${esc(r.label)}: ${r.value}" title="${esc(r.label)}: ${r.value}"><div><span>${esc(r.label)}</span><strong>${r.value}</strong></div><div class="admin-analytics-track"><span style="width:${Number(r.value)/maximum*100}%"></span></div></div>`).join('');
  }
  function paint(d,filters){
    const statusLabel=filters.status?labels[filters.status]:'Tất cả trạng thái',active=d.statuses.filter(r=>r.status!=='cancelled').reduce((n,r)=>n+r.count,0),completed=d.statuses.find(r=>r.status==='completed')?.count||0,cancelled=d.statuses.find(r=>r.status==='cancelled')?.count||0;
    const rating=d.reviewCount?Number(d.rating).toLocaleString('vi-VN',{minimumFractionDigits:1,maximumFractionDigits:1}):'—';
    $('#report-period').textContent=`Kỳ: ${dateLabel(d.start)} — ${dateLabel(d.end)} · ${statusLabel}`;
    const stats=[['Doanh thu đã thanh toán',money(d.revenue),'Theo ngày thanh toán Việt Nam','wallet'],['Lịch hẹn',d.appointments,'Theo ngày hẹn · '+statusLabel,'calendar'],['Lượt đặt không hủy',active,'Không gồm lịch đã hủy','leaf'],['Điểm trải nghiệm',d.reviewCount?rating+' / 5':'—',d.reviewCount+' đánh giá · theo ngày gửi','star']];
    $('#report-stats').innerHTML=stats.map(([label,value,caption,symbol],i)=>`<article class="admin-finance-stat ${i?'':'is-featured'}"><div class="admin-finance-stat-heading"><span>${label}</span>${icon(symbol)}</div><strong>${esc(value)}</strong><p>${esc(caption)}</p></article>`).join('');
    const allEmpty=!d.appointments&&!d.daily.length&&!d.reviewCount;
    $('#report-empty').hidden=!allEmpty;
    $('#report-content').classList.toggle('is-empty',allEmpty);
    $('.admin-report-insights').hidden=allEmpty;
    $('#report-status-caption').textContent='Theo ngày hẹn · '+statusLabel;
    const maxRevenue=Math.max(1,...d.daily.map(r=>Number(r.total)));
    $('#report-revenue').innerHTML=d.daily.length?`<div class="admin-revenue-days">${d.daily.map(r=>`<div class="admin-revenue-day" tabindex="0" aria-label="${dateLabel(r.day)}: ${money(r.total)}"><div class="admin-revenue-day-label"><span>${icon('calendar')}${dateLabel(r.day)}</span><strong>${money(r.total)}</strong></div><div class="admin-analytics-track"><span style="width:${Number(r.total)/maxRevenue*100}%"></span></div></div>`).join('')}</div>`:empty('Chưa có doanh thu trong kỳ.','wallet');
    $('#report-status').innerHTML=d.appointments?bars(d.statuses.map(r=>({label:labels[r.status],value:r.count,tone:r.status}))):empty(filters.status?'Không có lịch '+statusLabel.toLocaleLowerCase('vi')+'.':'Chưa có lịch hẹn trong kỳ.','calendar');
    $('#report-services').innerHTML=d.popular.length?bars(d.popular.map(r=>({label:r.service__name,value:r.count,tone:'positive'}))):empty('Chưa có lượt đặt không hủy.','leaf');
    $('#report-ratings').innerHTML=d.reviewCount?bars([5,4,3,2,1].map(n=>({label:`${n} sao`,value:d.ratings.find(r=>r.rating===n)?.count||0,tone:n>=4?'positive':n===3?'neutral':'negative'}))):empty('Chưa có đánh giá trong kỳ.','star');
    $('#report-rows').innerHTML=d.report.map(r=>`<tr><th scope="row">${esc(r.service)}</th><td>${r.appointments}</td><td>${r.active}</td><td>${r.completed}</td><td>${money(r.revenue)}</td><td>${r.reviews}</td><td>${r.reviews?Number(r.rating).toLocaleString('vi-VN',{minimumFractionDigits:1,maximumFractionDigits:1}):'—'}</td></tr>`).join('')||'<tr><td colspan="7" class="report-table-empty">Chưa có dịch vụ để tổng hợp.</td></tr>';
    $('#report-total').innerHTML=`<tr><th scope="row">Tổng trong kỳ</th><td>${d.appointments}</td><td>${active}</td><td>${completed}</td><td>${money(d.revenue)}</td><td>${d.reviewCount}</td><td>${rating}</td></tr>`;
    const positive=d.ratings.filter(r=>r.rating>=4).reduce((n,r)=>n+r.count,0);
    $('#report-insights').innerHTML=allEmpty?'<p class="report-insights-empty">Chọn kỳ có dữ liệu để xem các điểm đáng chú ý.</p>':`<article>${icon('wallet')}<div><strong>${money(d.revenue)}</strong><p>Khoản thu hợp lệ trong kỳ thanh toán.</p></div></article><article>${icon('calendar')}<div><strong>${active} lượt đặt không hủy</strong><p>${completed} lịch hoàn thành · ${cancelled} lịch hủy, theo bộ lọc đã chọn.</p></div></article><article>${icon('star')}<div><strong>${d.reviewCount?positive+' / '+d.reviewCount+' đánh giá đạt 4–5 sao':'Chưa có đánh giá'}</strong><p>${d.reviewCount?'Tính từ số sao khách gửi trong kỳ.':'Điểm trải nghiệm chưa được xác định.'}</p></div></article>`;
  }
  async function load(retry=false){
    if(busy)return;
    let filters;const error=$('#report-filter-error');
    try{filters=retry&&lastRequest?lastRequest:getFilters();error.hidden=true;}
    catch(ex){error.textContent=ex.message;error.hidden=false;return;}
    const version=++revision;busy=true;lastRequest=filters;controls();$('#report-loading').hidden=false;$('#report-api-error').hidden=true;$('#report-content').hidden=true;
    try{
      const d=await api('/api/dashboard/?'+new URLSearchParams(filters));if(version!==revision)return;
      serverToday=d.today;paint(d,filters);$('#report-content').hidden=false;
      const url=new URL(location.href);for(const [key,value] of Object.entries(filters)){if(value)url.searchParams.set(key,value);else url.searchParams.delete(key);}history.replaceState(null,'',url);
    }catch(ex){if(version===revision){$('#report-api-error p').textContent=ex.message;$('#report-api-error').hidden=false;}}
    finally{if(version===revision){busy=false;controls();$('#report-loading').hidden=true;}}
  }
  for(const side of ['from','to']){
    $('#report-'+side).addEventListener('change',event=>{$('#report-'+side+'-display').value=dateLabel(event.target.value);});
    $('#report-'+side+'-display').addEventListener('input',event=>{$('#report-'+side).value=parseDisplay(event.target.value)||'';});
  }
  $('#report-filters').addEventListener('submit',event=>{event.preventDefault();load();});
  $('#report-reset').onclick=()=>{if(!busy){currentMonth();load();}};
  $('#report-retry').onclick=()=>load(true);
  const params=new URLSearchParams(location.search);
  if(params.has('start')||params.has('end')){
    for(const [side,key] of [['from','start'],['to','end']]){const value=params.get(key)||'';$('#report-'+side).value=value;$('#report-'+side+'-display').value=value?dateLabel(value):'';}
    const status=params.get('status')||'';$('#report-status-filter').value=Object.hasOwn(labels,status)?status:'';
  }else currentMonth();
  await load();
})();
