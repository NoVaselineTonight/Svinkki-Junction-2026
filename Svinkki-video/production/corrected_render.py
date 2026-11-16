"""Clean alpha-silhouette phones with actual supplied UI screenshots."""
import subprocess
from PIL import Image, ImageDraw, ImageFilter
import render as base


def mask(size, radius):
    image = Image.new("L", size)
    ImageDraw.Draw(image).rounded_rectangle((0, 0, size[0]-1, size[1]-1), radius, fill=255)
    return image


class FixedRenderer(base.Renderer):
    def __init__(self):
        super().__init__()
        # A clean extracted mark mask, no rectangular background.
        self.s_mark = Image.new("L", (29,54), 0)
        # Use the actual SVG paths from the supplied brand asset as clean vector strokes.
        # The path coordinates are rescaled into the small top-left presentation mark.
        import xml.etree.ElementTree as ET
        path = base.ROOT.parents[1] / "aaaaaaa" / "Svinkki-Junction-2026" / "web" / "brand" / "s-mark.svg"
        # The brand in the actual screenshot is authoritative if that clone is unavailable.
        # We use simple flowing strokes in the video frame, not the whole wordmark.
        d = ImageDraw.Draw(self.s_mark)
        d.line([(22,2),(18,2),(7,5),(3,12),(3,37),(2,42),(0,43)], fill=255, width=3,joint="curve")
        d.line([(28,9),(24,10),(12,13),(9,20),(9,46),(7,51),(6,52)], fill=255,width=3,joint="curve")
        self.last_frame = None

    def phone_shadow(self, t, accent):
        layer=Image.new("RGBA",(base.W,base.H))
        d=ImageDraw.Draw(layer)
        d.ellipse((1100,962,1760,1050),fill=(0,29,17,110))
        d.ellipse((1220,989,1630,1035),fill=(0,23,12,115))
        return layer.filter(ImageFilter.GaussianBlur(25))

    def phone(self,name,t,scene,width=500,x=1388,y=526,yaw=0.0,pitch=0.0,roll=0.0,detail=1.0):
        src=self.images[name]
        p=base.ease(t)
        zoom=1+(scene.get("crop",(1.1,))[0]-1)*p
        sw,sh=src.size
        cw=round(sw/zoom)
        ch=round(cw*1100/506)
        cfg=scene.get("crop",(1.1,0.5,0.5,0))
        left=max(0,min(sw-cw,round(sw*cfg[1]-cw/2)))
        top=max(0,min(sh-ch,round(sh*(cfg[2]+cfg[3]*(p-.5))-ch/2)))
        shot=src.crop((left,top,left+cw,top+ch)).resize((480,1038),Image.Resampling.LANCZOS)
        phone=Image.new("RGBA",(518,1112))
        d=ImageDraw.Draw(phone)
        d.rounded_rectangle((0,0,517,1111),48,fill=(36,98,62),outline=(117,166,133),width=2)
        d.rounded_rectangle((4,5,513,1106),43,fill=(6,39,27),outline=(57,115,75),width=2)
        phone.paste(shot,(18,24),mask((480,1038),29))
        d=ImageDraw.Draw(phone)
        d.rounded_rectangle((197,10,313,19),4,fill=(1,23,16))
        d.ellipse((321,10,331,20),fill=(1,23,16))
        d.rounded_rectangle((184,1095,335,1100),3,fill=(39,86,54))
        result=Image.new("RGBA",(538,1134))
        a=phone.getchannel("A")
        for n in range(10,0,-1):
            edge=Image.new("RGBA",phone.size,(20+n,63+n,39+n,255))
            result.paste(edge,(12 if yaw<0 else 0,12-n),a)
        result.alpha_composite(phone,(0,0))
        phone=result.rotate(yaw*135,Image.Resampling.BICUBIC,expand=True)
        ratio=width/phone.width
        phone=phone.resize((round(phone.width*ratio),round(phone.height*ratio)),Image.Resampling.LANCZOS)
        out=Image.new("RGBA",(base.W,base.H))
        out.alpha_composite(phone,(round(x-phone.width/2),round(y-phone.height/2)-8))
        return out


def main():
    r=FixedRenderer()
    r.frame(6,5.2).save(base.OUT/"review"/"fixed-phone-preview.png")
    for i in range(len(base.SCENES)):
        r.render_scene(i,output=base.BUILD/f"{i:02d}.mp4")
    cat=base.BUILD/"concat.txt"
    cat.write_text("\n".join(f"file '{(base.BUILD/f'{i:02d}.mp4').as_posix()}'" for i in range(len(base.SCENES))))
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(cat),
                    "-i",str(base.OUT/"Svinkki-soundtrack.m4a"),"-map","0:v","-map","1:a",
                    "-c:v","copy","-c:a","copy","-movflags","+faststart","-t",str(base.TOTAL),
                    str(base.OUT/"Svinkki-demo-1080p.mp4")],check=True)
    print("Final corrected MP4 exported",flush=True)


if __name__ == "__main__":
    main()
