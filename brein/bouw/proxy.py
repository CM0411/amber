"""Proefopstelling: de nieuwe pagina lokaal, de gegevens live van de Z490.
   python3 proxy.py 8779  -> http://localhost:8779/"""
import sys, http.server, urllib.request, pathlib
POORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8779
BRON = "http://192.168.1.239:8000"
HIER = pathlib.Path(__file__).parent
MELDER = b"<script>setTimeout(function(){var orig=tekenRuimte,som=0,n=0,max=0;tekenRuimte=function(){var t0=performance.now();orig.apply(null,arguments);var d=performance.now()-t0;som+=d;n++;if(d>max)max=d;};setTimeout(function(){var d=document.createElement('div');d.id='tijd';d.textContent='tekenRuimte gemiddeld '+(som/n).toFixed(2)+' ms, max '+max.toFixed(1)+' ms over '+n+' beelden';document.body.appendChild(d);},3000);},1500);setTimeout(function(){try{var d=document.createElement('div');d.id='peil';var px=function(x,y){return Array.from(ctx.getImageData(Math.round(x),Math.round(y),1,1).data);};var wq=wolkDoek.getContext('2d').getImageData(0,0,wolkDoek.width,wolkDoek.height).data,wn=0;for(var i=3;i<wq.length;i+=4)if(wq[i]>0)wn++;d.textContent=JSON.stringify({cel:G.cel,wolkV0:G.wolkV0,wolkRijen:G.wolkRijen,wolkRect:G.wolk,pxWolkOnder:px(G.wolk[0]+4,G.wolk[1]+G.wolk[3]-6),pxWolkMidden:px(G.wolk[0]+40,G.wolk[1]+G.wolk[3]/2),wolkTekst:wolkTekst,antwoordNu:antwoordNu,wolkPixels:wn,wolkDoek:[wolkDoek.width,wolkDoek.height],pxPunt:px(G.punt[0],G.punt[1]),pxKnoop:px(G.knoop[0][0][0],G.knoop[0][0][1]),pxMidden:px(600,400),vezelPx:Array.from(vezelDoek.getContext('2d').getImageData(Math.round(G.knoop[3][5][0]),Math.round(G.knoop[3][5][1]),1,1).data),doek:[doek.width,doek.height],P:P,knoop0:G.knoop&&G.knoop[0][0],knoop20:G.knoop&&G.knoop[20][31],punt:G.punt,uit:G.uit,wolk:G.wolk,glad:glad.length,vezel:[vezelDoek.width,vezelDoek.height],opbouw:opbouw,beelden:beelden,staand:G.staand,gloeiS:G.gloeiS,cel:G.cel});document.body.appendChild(d);}catch(e){var d=document.createElement('div');d.id='peil';d.textContent='PEILFOUT '+e;document.body.appendChild(d);}},3000);window.onerror=function(m,s,l,c){var d=document.createElement('div');d.id='fout';d.textContent='FOUT '+m+' @'+l+':'+c;document.body.appendChild(d);};</script>"
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        pad = self.path.split("?")[0]
        if pad == "/" or pad.startswith("/index"):
            b = (HIER / "index-v3.html").read_bytes().replace(b"<head>", b"<head>" + (MELDER if "peil=1" in self.path else b""), 1)
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b); return
        try:
            with urllib.request.urlopen(BRON + self.path, timeout=10) as r:
                b = r.read(); soort = r.headers.get("Content-Type", "application/octet-stream")
            self.send_response(200); self.send_header("Content-Type", soort); self.send_header("Content-Length", str(len(b))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(b)
        except Exception as e:
            self.send_response(502); self.end_headers(); self.wfile.write(str(e).encode())
http.server.ThreadingHTTPServer(("127.0.0.1", POORT), H).serve_forever()
