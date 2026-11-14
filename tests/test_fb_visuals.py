"""Lane VISUALS: web/visuals.js (chart library and visual answer cards) is wired in, served, safe, and works."""
import json
import os as _os
import shutil
import subprocess
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fixture as fx  # noqa: E402

WEB = fx.REPO / "web"
JS = (WEB / "visuals.js").read_text(encoding="utf-8")
CSS = (WEB / "visuals.css").read_text(encoding="utf-8")
NODE = shutil.which("node")

CARD_TYPES = ("spend overview baskets safe_to_spend afford what_if save_more spender_type averages benchmarks leaks "
              "receipt_insights money_story season_outlook category_story explain_month low_points income_profile "
              "receipt_trends basket_profile cut_ideas findings").split()


class VisualsStatic(unittest.TestCase):
    def test_globals(self):
        self.assertRegex(JS, r"window\.SvinkkiVisuals\s*=\s*\{")
        self.assertIn("window.SvinkkiCards = window.SvinkkiCards || {}", JS)
        self.assertIn("drawChart", JS)

    def test_no_markup_injection(self):
        self.assertNotRegex(JS, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")

    def test_load_order_in_the_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("visuals.js"), html.index('src="app.js"'))
        self.assertIn("visuals.css", html)

    def test_card_types_registered(self):
        for t in CARD_TYPES:
            self.assertTrue(f"{t}:" in JS or f"'{t}'" in JS or f" {t}: " in JS, t)

    def test_no_small_text(self):
        import re
        for m in re.finditer(r"font-size:\s*([\d.]+)px", CSS):
            self.assertGreaterEqual(float(m.group(1)), 12, m.group(0))


class VisualsServed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_both_files_are_served(self):
        for path, kind in (("/visuals.js", "javascript"), ("/visuals.css", "text/css")):
            r = self.server.client().get(path)
            self.assertEqual(r.status, 200, path)
            self.assertRegex(r.header("Content-Type"), kind)


FAKE = r"""
class El { constructor(tag){this.tag=tag;this.attrs={};this.children=[];this.className='';this._t='';}
  setAttribute(k,v){this.attrs[k]=String(v); if(k==='class')this.className=String(v);}
  appendChild(c){this.children.push(c);return c;}
  set textContent(v){this._t=String(v);} get textContent(){return this._t+this.children.map(c=>c.textContent).join('');}
  get childNodes(){return this.children;} }
class Tx { constructor(s){this.s=s;this.attrs={};this.className='';this.children=[];} get textContent(){return this.s;} }
global.Node = El;
global.document={createElement:t=>new El(t),createElementNS:(n,t)=>new El(t),createTextNode:s=>new Tx(s),addEventListener(){}};
let FI=false;
const walk=(e,f)=>{f(e);(e.children||[]).forEach(c=>walk(c,f));};
global.walk=walk; global.setFi=v=>{FI=v;};
global.window={SvinkkiApp:{
  h(tag,props,...kids){const e=new El(tag);for(const k in (props||{})){if(props[k]!=null&&props[k]!==false)e.setAttribute(k,props[k]);}
    const add=k=>{if(k==null||k===false)return;if(Array.isArray(k))return k.forEach(add);e.appendChild(typeof k==='string'?new Tx(k):(typeof k==='number'?new Tx(String(k)):k));};kids.forEach(add);return e;},
  svgEl(n,a){const e=new El(n);for(const k in a)e.setAttribute(k,a[k]);return e;},
  T:s=>s, isFi:()=>FI, money:(n,o)=>(FI?String(Math.round(n)).replace('.',',')+' €':'€'+Math.round(n)), euros:n=>'€'+Math.round(n),
  fmtMonth:ym=>{const m=+ym.slice(5,7);const E=['January','February','March','April','May','June','July','August','September','October','November','December'];
    const F=['tammikuu','helmikuu','maaliskuu','huhtikuu','toukokuu','kesäkuu','heinäkuu','elokuu','syyskuu','lokakuu','marraskuu','joulukuu'];return (FI?F:E)[m-1]+(ym.startsWith('2025')?' 2025':'');},
  fmtDate:s=>s,
  cardShell(title,sub,cls){const c=new El('section');c.className='card '+(cls||'');c.appendChild(new El('h3')).appendChild(new Tx(title));return c;},
  keyFig(c,v,l){const k=new El('div');k.className='key';k.appendChild(new Tx(v+(l?' '+l:'')));c.appendChild(k);},
  more(c,nodes,d){const m=new El('details');m.className='more';(function f(x){(Array.isArray(x)?x:[x]).forEach(n=>{if(n==null||n===false)return;if(Array.isArray(n))return f(n);m.appendChild(n);});})(nodes);c.appendChild(m);return c;}
}};
require(%s);
const V=window.SvinkkiVisuals, T=V._test;
"""


@unittest.skipUnless(NODE, "node is not installed")
class VisualsPure(unittest.TestCase):
    def run_js(self, body):
        code = FAKE % json.dumps(str(WEB / "visuals.js")) + body
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_labels_and_scales(self):
        out = self.run_js("""console.log(JSON.stringify({
          a:T.shortMonth('August 2025'),b:T.shortMonth('elokuu'),c:T.shortMonth('May'),d:T.monthLabel('2026-08'),
          e:T.scaleMax([0,0]),f:T.scaleMax([3,'x',null,12.5]),
          g:T.fmtVal(92.85,'eur'),h:T.fmtVal(4,'count'),i:T.fmtVal(37.6,'pct'),j:T.fmtVal(null,'eur'),
          k:[0,1,2,3,4,5,6,7,8,9,10,11].map(i=>T.showLabelAt(i,12,false)),
          l:T.showLabelAt(0,12,true),m:[0,1,2].map(i=>T.showLabelAt(i,3,false)),
          n:T.toneOf({tone:'good'},true),o:T.toneOf({mark:true},true),p:T.toneOf({},true),q:T.toneOf({},false)}))""")
        self.assertEqual((out["a"], out["b"], out["c"], out["d"]), ("Aug", "elo", "May", "Aug"))
        self.assertEqual((out["e"], out["f"]), (1, 12.5))
        self.assertEqual((out["g"], out["h"], out["i"], out["j"]), ("€93", "4", "38%", ""))
        self.assertEqual(out["k"].count(True), 6)
        self.assertTrue(out["k"][-1])
        self.assertTrue(out["l"])
        self.assertEqual(out["m"], [True, True, True])
        self.assertEqual((out["n"], out["o"], out["p"], out["q"]), ("good", "main", "muted", "main"))

    def test_geometry_stays_inside(self):
        out = self.run_js("""const r=[];for(const n of [2,7,12]){for(const two of [false,true]){
          const g=T.barGeometry(n,280,6,two);const last=g.x(n-1,two)+g.bw;r.push([g.x(0,false)>=6,last<=274,g.bw<=34]);}}
          console.log(JSON.stringify(r))""")
        for row in out:
            self.assertEqual(row, [True, True, True])

    def test_smooth_path_never_leaves_the_neighbours(self):
        out = self.run_js("""const d=T.smoothPath([[0,50],[50,10],[100,10],[150,90]]);
          const nums=d.match(/-?\\d+\\.\\d/g).map(Number);console.log(JSON.stringify({d:d,ys:nums.filter((_,i)=>i%2===1),n:T.smoothPath([])}))""")
        self.assertTrue(out["d"].startswith("M0.0,50.0 C"))
        self.assertTrue(all(10 <= y <= 90 for y in out["ys"]), out["ys"])
        self.assertEqual(out["n"], "")

    def test_valid_chart_gate(self):
        out = self.run_js("""const s=(n,v)=>Array.from({length:n},(_,i)=>({label:'p'+i,value:v==null?i+1:v}));
          console.log(JSON.stringify({
            none:T.validChart(null), unk:T.validChart({kind:'pie',series:s(3)}),
            bars1:T.validChart({kind:'bars',series:s(1)}), bars2:!!T.validChart({kind:'bars',series:s(2)}),
            cap:T.validChart({kind:'bars',series:s(20)}).series.length, hcap:T.validChart({kind:'hbars',series:s(9)}).series.length,
            split1:T.validChart({kind:'split',series:[{label:'a',value:5},{label:'b',value:0}]}),
            prog:!!T.validChart({kind:'progress',now:10,target:100,series:[]}), prog0:T.validChart({kind:'progress',now:10,target:0}),
            bad:T.validChart({kind:'line',series:[{value:'x'},{value:null}]})}))""")
        for k in ("none", "unk", "bars1", "split1", "prog0", "bad"):
            self.assertIsNone(out[k], k)
        self.assertTrue(out["bars2"] and out["prog"])
        self.assertEqual((out["cap"], out["hcap"]), (12, 6))

    def test_every_kind_draws(self):
        out = self.run_js("""
          const M=(ym,v,o)=>Object.assign({ym,value:v,label:null},o||{});
          const charts={
            bars:{kind:'bars',unit:'eur',series:[M('2026-03',120),M('2026-04',90),M('2026-05',200,{mark:true}),M('2026-06',0)],target:110},
            bars2:{kind:'bars',unit:'eur',series:[M('2026-03',120,{value2:300}),M('2026-04',90,{value2:280})],legend:{value:'Spent',value_fi:'Menot',value2:'Income',value2_fi:'Tulot'}},
            hbars:{kind:'hbars',unit:'eur',series:[{label:'Taxi',label_fi:'Taksit',value:92.85,value2:60},{label:'Food',value:40}]},
            line:{kind:'line',unit:'eur',series:[M('2026-03',100),M('2026-04',-50),M('2026-05',30)],target:null},
            linepos:{kind:'line',unit:'eur',series:[M('2026-03',100),M('2026-04',150),M('2026-05',130),M('2026-06',90),M('2026-07',99)]},
            split:{kind:'split',unit:'eur',series:[{label:'Bills',value:700},{label:'Left',value:300,tone:'good'}]},
            progress:{kind:'progress',unit:'eur',now:250,target:1000,series:[]}};
          const res={};
          for(const k in charts){const el=V.drawChart(charts[k],{caption:'Cap sentence.'});
            let tags={},texts=[],labels=[];walk(el,e=>{tags[e.tag]=(tags[e.tag]||0)+1;if(e.tag==='text')texts.push(e.textContent);if(e.attrs['aria-label'])labels.push(e.attrs['aria-label']);});
            res[k]={ok:!!el,tags,texts,labels,cls:el.className};}
          setFi(true);
          const f=V.drawChart(charts.hbars,{});let ft=[];walk(f,e=>{if(e.children&&e.children.length===1&&e.children[0].s!==undefined)ft.push(e.textContent);});
          const f2=V.drawChart(charts.bars2,{});let lg=[];walk(f2,e=>{if(/vz-leg-item/.test(e.className))lg.push(e.textContent);});
          const fm=V.drawChart(charts.bars,{});let ml=[];walk(fm,e=>{if(e.tag==='text')ml.push(e.textContent);});
          res.fi={ft,lg,ml};
          console.log(JSON.stringify(res))""")
        for k in ("bars", "bars2", "hbars", "line", "linepos", "split", "progress"):
            self.assertTrue(out[k]["ok"], k)
        b = out["bars"]
        self.assertEqual(b["tags"]["rect"], 4)
        self.assertIn("€200", b["texts"])           # the marked column carries its value
        self.assertEqual(b["texts"].count("€200"), 1)
        self.assertIn("€110", b["texts"])           # the dashed target is labelled
        self.assertIn("Mar", b["texts"])
        self.assertTrue(any(l.startswith("Cap sentence.") for l in b["labels"]))
        self.assertEqual(out["bars2"]["tags"]["rect"], 4)
        self.assertEqual(out["bars2"]["cls"], "vz vz-bars-wrap")
        # line with a negative value: zero line, two clipped paths
        ln = out["line"]
        self.assertEqual(ln["tags"]["path"], 2)
        self.assertEqual(ln["tags"]["clipPath"], 2)
        self.assertEqual(out["linepos"]["tags"]["path"], 1)
        self.assertNotIn("clipPath", out["linepos"]["tags"])
        self.assertEqual(out["split"]["tags"]["rect"], 2)
        self.assertEqual(out["progress"]["tags"]["circle"], 2)
        self.assertIn("25%", out["progress"]["texts"])
        # Finnish mode: Finnish labels, legend and month names
        self.assertIn("Taksit", " ".join(out["fi"]["ft"]))
        self.assertEqual([x for x in out["fi"]["lg"]], ["Menot", "Tulot"])
        self.assertIn("maa", out["fi"]["ml"])

    def test_cards(self):
        out = self.run_js("""
          const chart={kind:'bars',unit:'eur',series:[{ym:'2026-07',value:80},{ym:'2026-08',value:93,mark:true}]};
          const data={total:92.85,count:3,by_label:[{label:'Taxi',total:92.85,count:3}],period:{from:'2026-08-01',to:'2026-08-31'},
            chart,caption:'You spent 93 euros on taxis.',caption_fi:'Kulutit taksiin 93 euroa.'};
          const text=c=>c?c.textContent:null;
          const regs=Object.keys(window.SvinkkiCards||{});
          const en=window.SvinkkiCards.spend(data,{type:'spend'});
          setFi(true);
          const fi=window.SvinkkiCards.spend(data,{type:'spend'});
          const noFiCap=window.SvinkkiCards.spend(Object.assign({},data,{caption_fi:undefined}),{});
          const noChart=window.SvinkkiCards.spend({total:1,count:1},{});
          const story={highlights:['One English sentence.','Second one.','Third one.'],chart:null};
          const sFi=window.SvinkkiCards.money_story(story,{});
          const sFiCap=window.SvinkkiCards.money_story(Object.assign({caption_fi:'Suomeksi.'},story),{});
          setFi(false);
          const sEn=window.SvinkkiCards.season_outlook(story,{});
          const sNone=window.SvinkkiCards.findings({findings:[]},{});
          const aff=window.SvinkkiCards.afford({verdict:'yes',item:'phone',price:300,chart:{kind:'split',unit:'eur',series:[{label:'Phone',value:300},{label:'Left',value:192,tone:'good'}]},caption:'It fits.'},{});
          const mine=c=>{const r=[];walk(c,e=>{if(e.className&&/\\bmore\\b/.test(e.className))r.push(e.textContent);});return r[0]||'';};
          const outside=c=>{const t=[];walk(c,e=>{if(e.className&&/vz-caption/.test(e.className))t.push(e.textContent);});return t;};
          console.log(JSON.stringify({regs,en:text(en),fi:text(fi),enCap:outside(en),fiCap:outside(fi),noFiCap:outside(noFiCap),noChart:noChart,
            sFiCap:outside(sFi),sFiMore:mine(sFi),sFi2:outside(sFiCap),sEnCap:outside(sEn),sEnMore:mine(sEn),sNone:sNone,
            aff:text(aff),affV:(()=>{let v='';walk(aff,e=>{if(/verdict/.test(e.className))v=e.textContent;});return v;})()}))""")
        for t in CARD_TYPES:
            self.assertIn(t, out["regs"], t)
        self.assertEqual(out["enCap"], ["You spent 93 euros on taxis."])
        self.assertEqual(out["fiCap"], ["Kulutit taksiin 93 euroa."])
        self.assertEqual(out["noFiCap"], [])             # no English sentence in Finnish mode
        self.assertIsNone(out["noChart"])                # no chart: the built-in card draws it
        # story without chart, Finnish mode: no English sentence outside the fold, all of it behind More
        self.assertEqual(out["sFiCap"], [])
        self.assertIn("One English sentence.", out["sFiMore"])
        self.assertEqual(out["sFi2"], ["Suomeksi."])
        # English mode: first highlight is the sentence, the rest behind More
        self.assertEqual(out["sEnCap"], ["One English sentence."])
        self.assertIn("Second one.", out["sEnMore"])
        self.assertNotIn("One English sentence.", out["sEnMore"])
        self.assertIsNone(out["sNone"])
        self.assertEqual(out["affV"], "Yes")


if __name__ == "__main__":
    unittest.main()
