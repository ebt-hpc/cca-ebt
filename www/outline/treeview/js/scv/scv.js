/**
   Source code viewer for CCA/EBT.
   @author Masatomo Hashimoto <m.hashimoto@riken.jp>
   @copyright 2013-2017 RIKEN
   @licence Apache-2.0
*/

function SourceCodeViewer() {

}

function handleError(xhr, mes, err) {
  console.log("[scv.SourceCodeViewer] "+mes+" ("+err+")");
}

SourceCodeViewer.prototype.show = function(url, elem, mode, sline, eline, ranges) {
  var self = this;

  console.log("[scv.SourceCodeViewer] mode="+mode);
  console.log("[scv.SourceCodeViewer] url="+url);
  
  console.log("[scv.SourceCodeViewer] loading files...");

  $.ajax({
    type:"GET",
    mimeType:"text/plain",
    url:url,
    error:handleError
  }).done(function(src, status0, xhr0) {
    console.log("[scv.SourceCodeViewer] source file loaded.");

    self.cm = CodeMirror(elem,{
      value:src,
      mode:mode,
      lineNumbers:true,
      readOnly:true,
      scrollbarStyle:"simple",
      foldGutter:true,
      gutters: ["CodeMirror-linenumbers"],
    });

    // self.cm.on('dblclick', function (inst, ev) {
    //   console.log(inst);
    //   console.log(ev);
    // });

    if (sline > 0 && self.cm) {
        self.cm.scrollTo(0, self.cm.heightAtLine(sline - 1, "local"));
    }
    self.cm.markText({line:sline-1,ch:0},
                     {line:eline,ch:0},
                     {className:"styled-background"});

    if (self.cm.annotateScrollbar) {
      var sba = self.cm.annotateScrollbar('scrollbar-marks');
      sba.update([{from:{line:sline-1,ch:0},to:{line:eline,ch:0}}]);
    }

    //console.log(ranges);
    for (var i in ranges) {
      var range = ranges[i];
      var st = range.start;
      var ed = range.end;
      st.line -= 1;
      ed.line -= 1;
      ed.ch += 1;
      var obj = {};
      if (range.def) {
        //console.log(range.def);
        var ln = range.def.line;
        var a = document.createElement('a');
        a.setAttribute('class', 'range-background');
        a.innerHTML = self.cm.getDoc().getRange(st, ed);
        if (range.def.path) {
          var link = '', src = '', m;
          if (url.startsWith('/gitweb')) {
            m = url.match(/\/gitweb\/\?p=(.+);a=blob_plain;.+;hb=(.+)$/);
            if (m) {
              src =
                '/gitweb/?p='+m[1]+
                ';a=blob_plain;f='+range.def.path+
                ';hb='+m[2];
            }
 
          } else if (url.startsWith('projects')) {
            m = url.match(/projects\/(.+)\/(.+)\/.+$/);
            if (m) {
              src = 'projects/'+m[1]+'/'+m[2]+'/'+range.def.path;
            }
          }
          if (src) {
            link =
              'openviewer?path='+encodeURIComponent(range.def.path)+
              '&src='+encodeURIComponent(src)+
              '&ver='+m[2]+
              '&startl='+ln+'&endl='+ln;
            console.log(link);
          }

          a.setAttribute('href', link);
          a.setAttribute('target', '_blank');

          var code = range.def.code ? range.def.code : '???';
          a.title = code+' ['+ln+':'+range.def.path+']';

          obj.replacedWith = a;

        } else {
          var act = 'scv.cm.scrollTo(0,scv.cm.heightAtLine('+(ln-1)+',"local"));';
          a.setAttribute('onclick', act);
          a.title = self.cm.getLine(ln-1).replace(/^\s*|\s*$/g, '')+' ['+ln+']';

          obj.replacedWith = a;
        }
      } else {
        obj.className = 'range-background';
        var name = self.cm.getDoc().getRange(st, ed);
        var c = name.charCodeAt(0);
        var ty = 'real';
        if (105 <= c && c <= 110) {
          ty = 'int'
        }
        obj.title = ty+'?';
      }
      self.cm.markText(st,ed,obj);
    }

    var h = getPageHeight();
    self.cm.setSize("100%", h*0.85);

  })

}

