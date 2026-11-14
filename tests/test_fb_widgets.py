"""Lane WIDGETS: web/widgets.js (home dashboard, plan builder, add-to-home buttons) is wired in, safe and correct."""
import json
import os as _os
import shutil
import subprocess
import sys as _sys
import unittest

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import fixture as fx  # noqa: E402

WEB = fx.REPO / "web"
JS = (WEB / "widgets.js").read_text(encoding="utf-8")
CSS = (WEB / "widgets.css").read_text(encoding="utf-8")
NODE = shutil.which("node")

# A minimal DOM and a SvinkkiApp with the real h() contract (strings become text nodes), enough to draw the widgets.
HARNESS = r"""
function mk(tag){var e={tagName:tag,children:[],attrs:{},style:{},listeners:{},className:'',hidden:false,isConnected:true,
 _text:null,parent:null,
 get firstChild(){return this.children[0]||null;},
 appendChild(c){if(c.isFrag){c.children.slice().forEach(x=>this.appendChild(x));c.children=[];return c;}c.parent=this;this.children.push(c);return c;},
 removeChild(c){this.children=this.children.filter(x=>x!==c);return c;},
 replaceChildren(){this.children=[];Array.prototype.slice.call(arguments).forEach(x=>this.appendChild(x));},
 setAttribute(k,v){this.attrs[k]=String(v);if(k==='class')this.className=v;},
 getAttribute(k){return this.attrs[k]==null?null:this.attrs[k];},
 addEventListener(t,f){(this.listeners[t]=this.listeners[t]||[]).push(f);},
 click(){(this.listeners.click||[]).forEach(f=>f({}));},
 remove(){if(this.parent)this.parent.removeChild(this);},
 querySelector(sel){var cls=sel.replace('.','');var f=null;(function w(n){n.children.forEach(c=>{if(!f&&c.className&&(' '+c.className+' ').indexOf(' '+cls+' ')>=0)f=c;w(c);});})(this);return f;},
 set textContent(t){this.children=[];this._text=String(t);},
 get textContent(){return (this._text||'')+this.children.map(c=>c.textContent).join('');}};
 return e;}
function mkText(t){return {isText:true,children:[],textContent:String(t),parent:null};}
global.document={createElement:mk,createElementNS:(ns,t)=>mk(t),createTextNode:mkText,createDocumentFragment:()=>{var f=mk('#frag');f.isFrag=true;return f;},addEventListener(){}};
global.Node=function(){};
function walk(n,f){f(n);(n.children||[]).forEach(c=>walk(c,f));}
function all(n,pred){var o=[];walk(n,x=>{if(pred(x))o.push(x);});return o;}
function app(fi,calls,routes){
 function add(el,kids){kids.forEach(k=>{if(k==null||k===false)return;if(Array.isArray(k))return add(el,k);
   if(k.children!==undefined)el.appendChild(k);else el.appendChild(mkText(String(k)));});}
 return {isFi:()=>fi,
  h(tag,props){var e=mk(tag);if(props)for(var k in props){var v=props[k];if(v==null||v===false)continue;
    if(k==='class')e.className=v;else if(k.slice(0,2)==='on')e.addEventListener(k.slice(2).toLowerCase(),v);else e.setAttribute(k,v===true?'':v);}
    add(e,Array.prototype.slice.call(arguments,2));return e;},
  svgEl(n,a){var e=mk(n);for(var k in a)e.setAttribute(k,a[k]);return e;},
  api(path,o){calls.push([path,o&&o.body]);var r=routes[path];if(r instanceof Error)return Promise.reject(r);
    return r===undefined?Promise.reject(new Error('404')):Promise.resolve(typeof r==='function'?r(o):r);},
  euros:n=>Math.round(n)+' EUR',money:n=>Math.round(n)+' EUR',fmtMonth:s=>s,fmtDate:s=>s,icon:()=>null,
  me:()=>({today:'2026-11-14'}),refreshHome(){calls.push(['refreshHome']);},openSheet(t){calls.push(['sheet',t]);return mk('div');},
  closeSheet(){},moneyProposalCard(p){var e=mk('section');e.className='money-card';return e;},ask(t){calls.push(['ask',t]);}};
}
global.window={};
require(%(path)s);
const W=window.SvinkkiWidgets, T=W._test;
const tick=()=>new Promise(r=>setTimeout(r,5));
"""

PLAN_WIDGETS = r"""[{id:'goal',type:'plan',title:'Buffer',data:{name:'Buffer',target:1000,saved:200,monthly:100,months_left:8,pct:20,status:'on_track',
  status_text:'On track',status_text_fi:'Aikataulussa',series:[{ym:'2026-11',planned:200,actual:200},{ym:'2026-12',planned:300,actual:null},{ym:'2027-01',planned:400,actual:null}],
  next_move:{amount:50,ok:true,text:'Move 50 now',text_fi:'Siirrä 50 nyt'}}},
  {id:'w1',type:'safe',title:'Safe to spend',data:{chart:{kind:'split',unit:'eur',series:[{label:'Bills',value:300},{label:'Safe',value:500,tone:'good'}]},caption:'You can spend 500.'}}]"""


@unittest.skipUnless(NODE, "node is not installed")
class WidgetsNode(unittest.TestCase):
    def run_js(self, body):
        code = HARNESS % {"path": json.dumps(str(WEB / "widgets.js"))} + "\n(async()=>{" + body + "})().catch(e=>{console.error(e);process.exit(1)});"
        r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def test_plan_maths_matches_the_server(self):
        out = self.run_js("""
          console.log(JSON.stringify([T.monthsFor(1000,0,250),T.monthsFor(1000,100,250),T.monthsFor(1000,1000,10),
            T.monthsFor(1000,0,0)===Infinity,T.addMonths('2026-11',3),T.addMonths('2026-11',2),T.monthsBetween('2026-11','2027-05'),
            T.defaultMonthly(1200,0,'2027-11-01','2026-11'),T.defaultMonthly(600,0,null,'2026-11')]));""")
        self.assertEqual(out, [4, 4, 0, True, "2027-02", "2027-01", 6, 100, 50])

    def test_slider_range_and_projection(self):
        out = self.run_js("""
          var r=T.sliderRange(1000,0,50), r2=T.sliderRange(100,0,500);
          var p=T.projection(1000,0,250);
          console.log(JSON.stringify([r.min,r.max>=330,r.step, r2.max>=500, T.clampMonthly(7,r), T.clampMonthly(99999,r)<=r.max,
            p.length, p[0].planned, p[p.length-1].planned, p[p.length-1].i, T.projection(500,0,10).length<=37]));""")
        self.assertEqual(out, [10, True, 5, True, 10, True, 5, 0, 1000, 4, True])

    def test_card_to_widget_mapping(self):
        out = self.run_js("""
          console.log(JSON.stringify([T.widgetFor({type:'safe_to_spend',data:{}}), T.widgetFor({type:'baskets',data:{}}),
            T.widgetFor({type:'overview',data:{}}),
            T.widgetFor({type:'spend',data:{by_label:[{label:'Taxi',total:9}]}}),
            T.widgetFor({type:'spend',data:{by_label:[{label:'Taxi',total:9},{label:'Food',total:4}]}}),
            T.widgetFor({type:'goal_plan',data:{}})]));""")
        self.assertEqual(out, [{"type": "safe"}, {"type": "baskets"}, {"type": "baskets"},
                               {"type": "category", "params": {"label": "Taxi"}}, None, None])

    def test_home_draws_plan_suggestions_and_buttons(self):
        out = self.run_js(r"""
          var calls=[];
          var W_LIST=""" + PLAN_WIDGETS + r""";
          var routes={'/api/widgets':function(o){return o&&o.method==='POST'?{widget:{id:'w9',type:'plan',data:{}}}:{can_add:['plan','safe'],widgets:W_LIST};},
            '/api/next-steps':{steps:[{id:'s1',title:'Start a buffer',why:'Surprises happen.',figure:{value:50,unit:'eur'},
              action:{type:'create_widget',widget:{type:'plan',params:{name:'x',target:500}},label:'Add plan'}},
              {id:'s2',title:'Ask',why:'',action:{type:'ask',message:'hello',label:'Ask'}}]},
            '/api/widgets/move':{proposal:{id:'p',amount:50}},'/api/next-steps/dismiss':{ok:true}};
          window.SvinkkiApp=app(true,calls,routes);
          var box=mk('div');box.hidden=true;
          W.home(box);await tick();
          var txt=box.textContent;
          var btns=all(box,n=>n.tagName==='button');
          var move=btns.filter(b=>/Siirrä/.test(b.textContent))[0];
          move.click();await tick();
          var addBtn=btns.filter(b=>b.textContent==='Add plan')[0];addBtn.click();await tick();
          var not=btns.filter(b=>b.textContent==='Not now'||b.textContent==='Ei nyt')[0];not.click();await tick();
          console.log(JSON.stringify({hidden:box.hidden,fi:/Aikataulussa/.test(txt),sugg:/Start a buffer/.test(txt),
            svg:all(box,n=>n.tagName==='svg').length>=2,caption:/You can spend 500/.test(txt),
            moved:calls.some(c=>c[0]==='/api/widgets/move'&&c[1].id==='goal'&&c[1].amount===50),
            money:all(box,n=>n.className==='money-card').length,
            created:calls.some(c=>c[0]==='/api/widgets'&&c[1]&&c[1].type==='plan'),
            dismissed:calls.some(c=>c[0]==='/api/next-steps/dismiss'&&c[1].id==='s1')}));""")
        self.assertFalse(out["hidden"])
        for k in ("fi", "sugg", "svg", "caption", "moved", "created", "dismissed"):
            self.assertTrue(out[k], k)
        self.assertEqual(out["money"], 1)

    def test_empty_state_and_failures_never_throw(self):
        out = self.run_js(r"""
          var calls=[];
          window.SvinkkiApp=app(false,calls,{'/api/widgets':{widgets:[{id:'goal',type:'plan',title:'',data:{target:null,saved:0}}],can_add:['plan']}});
          var box=mk('div');W.home(box);await tick();
          var t1=box.textContent;
          var presets=all(box,n=>n.className==='wg-preset');presets[0].click();
          window.SvinkkiApp=app(false,[],{});
          var box2=mk('div');W.home(box2);await tick();
          window.SvinkkiApp=null; W.home(mk('div')); W.afterCard(mk('div'),{type:'safe_to_spend'});
          console.log(JSON.stringify({empty:/Start a savings plan/.test(t1)&&/Buffer for surprises/.test(t1)&&/loan/.test(t1),
            presets:presets.length, sheet:calls.some(c=>c[0]==='sheet'), hidden2:box2.hidden===true&&!box2.firstChild}));""")
        self.assertTrue(out["empty"])
        self.assertEqual(out["presets"], 3)
        self.assertTrue(out["sheet"])
        self.assertTrue(out["hidden2"])

    def test_builder_slider_recomputes_and_saves(self):
        out = self.run_js(r"""
          var calls=[];
          var routes={'/api/plan/preview':{fits:true,note:'Fits your month.',note_fi:'Sopii kuukauteesi.'},
            '/api/widgets':function(o){return {widget:{id:'goal',type:'plan',data:{name:'Trip'}}};}};
          window.SvinkkiApp=app(false,calls,routes);
          var card=window.SvinkkiCards.plan_offer({name:'Trip',target:1000,monthly:100,deadline:'2027-09-01'},{type:'plan_offer'});
          var none=window.SvinkkiCards.goal_plan({needs:['target'],monthly_needed:null},{});
          var slider=all(card,n=>n.tagName==='input'&&n.attrs.type==='range')[0];
          var before=card.textContent;
          slider.value='250';(slider.listeners.input||[]).forEach(f=>f({}));
          var after=card.textContent;
          (slider.listeners.change||[]).forEach(f=>f({}));await tick();
          var fit=/Fits your month/.test(card.textContent);
          var submit=all(card,n=>n.tagName==='button')[0];submit.click();await tick();
          console.log(JSON.stringify({none:none,before:/100 EUR a month/.test(before)&&/Reached in 10 months/.test(before),
            after:/250 EUR a month/.test(after)&&/Reached in 4 months/.test(after),fit:fit,
            saved:calls.some(c=>c[0]==='/api/widgets'&&c[1]&&c[1].params&&c[1].params.monthly===250&&c[1].params.target===1000),
            refreshed:calls.some(c=>c[0]==='refreshHome'),home:/On your home page/.test(card.textContent)}));""")
        self.assertIsNone(out["none"])
        for k in ("before", "after", "fit", "saved", "refreshed", "home"):
            self.assertTrue(out[k], k)

    def test_after_card_adds_the_button_once(self):
        out = self.run_js(r"""
          var calls=[];
          window.SvinkkiApp=app(true,calls,{'/api/widgets':{widget:{id:'w2',type:'safe',data:{}}}});
          var node=mk('section');var c={type:'safe_to_spend',data:{}};
          W.afterCard(node,c);W.afterCard(node,c);
          var other=mk('section');W.afterCard(other,{type:'trend',data:{}});
          var b=all(node,n=>n.tagName==='button');b[0].click();await tick();
          console.log(JSON.stringify({n:b.length,label:b[0].textContent,none:all(other,n=>n.tagName==='button').length,
            posted:calls.some(c=>c[0]==='/api/widgets'&&c[1]&&c[1].type==='safe')}));""")
        self.assertEqual(out["n"], 1)
        self.assertEqual(out["label"], "Etusivullasi")
        self.assertEqual(out["none"], 0)
        self.assertTrue(out["posted"])


class WidgetsStatic(unittest.TestCase):
    def test_globals(self):
        self.assertIn("window.SvinkkiWidgets = {", JS)
        for name in ("home:", "afterCard:"):
            self.assertIn(name, JS)
        self.assertIn("window.SvinkkiCards.goal_plan", JS)
        self.assertIn("window.SvinkkiCards.plan_offer", JS)
        self.assertIn("window.SvinkkiCards = window.SvinkkiCards || {}", JS)

    def test_no_inner_html(self):
        self.assertNotRegex(JS, r"innerHTML|outerHTML|insertAdjacentHTML|document\.write")

    def test_load_order_in_the_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("styles.css"), html.index("widgets.css"))
        self.assertLess(html.index("widgets.js"), html.index('src="app.js"'))

    def test_css_has_tap_targets_and_tokens(self):
        self.assertIn("var(--green-strong)", CSS)
        self.assertIn("min-height: 44px", CSS)

    def test_finnish_is_registered(self):
        for fi in ("Säästösuunnitelmat", "Lisää etusivulle", "Svinkki ehdottaa", "Ei nyt", "Aloita säästösuunnitelma",
                   "Puskuri yllätyksiin", "kuukaudessa", "Muokkaa", "Siirrä"):
            self.assertIn(fi, JS)


class WidgetsServed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx.get()
        fx.use_fresh_state()
        cls.server = fx.Server()

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def test_both_files_are_served(self):
        for path, kind in (("/widgets.js", "javascript"), ("/widgets.css", "text/css")):
            r = self.server.client().get(path)
            self.assertEqual(r.status, 200, path)
            self.assertRegex(r.header("Content-Type"), kind)


if __name__ == "__main__":
    unittest.main()
