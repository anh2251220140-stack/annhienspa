"""Read-only loopback UI fixture. No Django, database, keys or real API.

Captures the current UI as 'before'; keep this process alive while editing for
before/after comparison. All API responses in the browser are synthetic memory.
"""
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "docs" / ("fr23-ui-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir()
    before = {"/before.js": (ROOT / "static/js/live-admin-reviews.js").read_bytes(),
              "/before.css": (ROOT / "static/css/admin-reviews-luxury.css").read_bytes()}
    for name, content in before.items():
        (output / name.lstrip("/")).write_bytes(content)
    original = (ROOT / "templates/pages/admin-reviews.html").read_text(encoding="utf-8")
    bootstrap = r'''
    <script>
    window.spaAuth={allowed:true,isAuthenticated:()=>true,getSession:()=>({role:'Admin'}),getProfile:()=>({})};
    window.spaCatalog={services:[],products:[]}; window.spaPromotions=[];
    const scenario=new URLSearchParams(location.search).get('case')||'mixed';
    const data=Array.from({length:5},(_,i)=>({id:i+1,rating:[5,2,4,1,5][i],customer:'Khách kiểm thử '+(i+1),service:'Liệu trình kiểm thử',appointmentId:i+1,comment:['Không gian yên tĩnh, chuyên viên nhẹ nhàng.','Tôi phải chờ lâu, mong Spa xác nhận giờ rõ hơn.','Một trải nghiệm thử nghiệm.','Nhận xét đã thay đổi.',''][i],createdAt:'2026-11-17T02:00:00Z',replies:[]}));
    const analyses=data.map((r,i)=>({reviewId:r.id,mode:i===2||i===4?'rule':'ai',sentiment:i===1||i===3?'negative':'positive',priority:i===1||i===3?'high':'low',themes:i===0?['Không gian','Thái độ nhân viên']:i===1?['Thời gian chờ']:['Theo số sao; chưa phân tích nội dung'],summary:i===0?'Khách ghi nhận không gian và sự nhẹ nhàng của chuyên viên.':i===1?'Khách góp ý về thời gian chờ; Admin cần kiểm tra bối cảnh.':'Chưa có phân tích AI. Quản trị viên cần đọc nhận xét gốc.',actions:i===0?['Ghi nhận phản hồi về không gian sau khi đối chiếu nhận xét.']:['Đọc đánh giá gốc và xác minh trước khi phản hồi.'],stale:i===3,analyzedAt:'2026-11-17T03:00:00Z',analysisState:i===4?'insufficient_text':'available'}));
    analyses[4].sentiment=null;analyses[4].priority=null;analyses[4].themes=[];analyses[4].summary='Không đủ căn cứ phân tích văn bản: đánh giá chưa có nhận xét.';
    if(scenario==='all-ai')analyses.forEach((a,i)=>Object.assign(a,{mode:'ai',stale:false,analysisState:'available',sentiment:i%2?'negative':'positive',themes:['Không gian'],summary:'Phân tích từ dữ liệu giả lập.'}));
    if(scenario==='all-rule')analyses.forEach(a=>Object.assign(a,{mode:'rule',stale:false}));
    let getCount=0,postCount=0;
    window.fetch=async(url,opts={})=>{
      const method=opts.method||'GET';let body;
      if(method==='GET'){getCount++;if(url==='/api/reviews/')body={items:scenario==='one'?data.slice(0,1):data};
      else {const m=/^\/api\/ai\/reviews\/(\d+)\/analyze\/$/.exec(url);if(!m)throw Error('Fixture blocks unknown request');body={analysis:scenario==='none'?null:analyses.find(a=>a.reviewId===Number(m[1]))};}}
      else if(url==='/api/ai/reviews/analyze/'&&method==='POST'){postCount++;const ids=JSON.parse(opts.body).reviewIds;body={items:analyses.filter(a=>ids.includes(a.reviewId))};}
      else throw Error('Fixture blocks unknown request');
      document.documentElement.dataset.fixtureRequests=JSON.stringify({get:getCount,post:postCount});
      return {ok:true,status:200,json:async()=>structuredClone(body)};
    };
    </script>'''

    def page(is_before):
        html = original if is_before else (ROOT / "templates/pages/admin-reviews.html").read_text(encoding="utf-8")
        html = re.sub(r"<script src=\"{% static 'js/(?:auth|live-data)\.js' %}\"></script>", "", html)
        html = re.sub(r"{{.*?}}", "", html)
        html = re.sub(r"{% static '([^']+)' %}", r"/static/\1", html)
        html = re.sub(r"{%.*?%}", "", html)
        html = html.replace('<script src="/static/js/phase4-api.js"', bootstrap + '<script src="/static/js/phase4-api.js"')
        if is_before:
            html = html.replace('/static/js/live-admin-reviews.js', '/before.js').replace('/static/css/admin-reviews-luxury.css', '/before.css')
        return html.encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlparse(self.path).path
            if path in ("/before/admin-reviews.html", "/after/admin-reviews.html"):
                content, mime = page(path.startswith("/before/")), "text/html; charset=utf-8"
            elif path in before:
                content, mime = before[path], "text/css" if path.endswith('.css') else "text/javascript"
            elif path.startswith('/static/'):
                target = (ROOT / path.lstrip('/')).resolve()
                if not target.is_relative_to((ROOT / 'static').resolve()) or not target.is_file():
                    self.send_error(404);return
                content, mime = target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            else:
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none'")
            self.end_headers();self.wfile.write(content)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    print(json.dumps({'url': f'http://127.0.0.1:{server.server_port}', 'evidence': str(output)}, ensure_ascii=True), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
