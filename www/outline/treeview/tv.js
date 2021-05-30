/**
   Outline tree viewer for CCA/EBT.
   @author Masatomo Hashimoto <m.hashimoto@riken.jp>
   @copyright 2013-2018 RIKEN
   @copyright 2018 Chiba Institute of Technology
   @licence Apache-2.0
*/

var HISTORY_SIZE = 3
var MAX_COMMENT_LIST_SIZE = 10;
var AJAX_TIMEOUT = 5000 //msec

var EXPAND_TARGET_LOOPS   = 'expand_target_loops'
var EXPAND_RELEVANT_LOOPS = 'expand_relevant_loops'
var EXPAND_ALL            = 'expand_all'
var COLLAPSE_ALL          = 'collapse_all'

var ALL     = 'All'
var CODE    = 'Code'
var COMMENT = 'Comment'

var ICONS_DIR = '../treeview/icons'

var USER = $('#user').text();
var PROJ = $('#proj').text();
var VER = $('#ver').text();

var PID = PROJ.replace(/_git$/, '.git');

var ua = window.navigator.userAgent.toLowerCase();
var safari = ua.indexOf("safari") != -1 && ua.indexOf("chrome") == -1;
var kernel_button_bg = $('#kernelButton').css('background-color');
var go_button_bg = $('#goButton').css('background-color');
var prev_button_bg = $('#prevButton').css('background-color');
var next_button_bg = $('#nextButton').css('background-color');
var clear_button_bg = $('#clearButton').css('background-color');


function Timer() {
  this.start_time = 0;
}
Timer.prototype.start = function () {
  this.start_time = window.performance.now();
}
Timer.prototype.get = function () {
  return (window.performance.now() - this.start_time);
}

var global_timer = new Timer();


function get_window_height() {
  var h = window.innerHeight ? window.innerHeight : $(window).height();
  return h;
}

function scrollTo(id, align_top) {
  var align_top = typeof align_top !== 'undefined' ? align_top : false;
  console.log('[scrollTo] id:', id);
  var pos = $('#'+id).position();
  console.log('[scrollTo] pos:', pos);
  if (pos) {
    var top = pos.top;
    var left = pos.left;
    if (align_top) {
      //top -= 24;
    } else {
      var h = get_window_height();
      top -= h / 2;
    }
    //console.log('scrollTo:', id, '->', top, left);
    $('html,body').animate({scrollTop:top,scrollLeft:left}, 0);
  }
}

function get_jstree() {
  return $('#outline').jstree(true);
}

function get_target_node(ev, jstree) {
  if (!jstree) {
    jstree = get_jstree();
  }
  console.log('get_target_node: ev.target='+ev.target);
  var li = $(ev.target).closest('li');
  var nd = jstree._model.data[li[0].id];
  return nd;
}

function reset_select_listeners() {
  $('select.estimation-scheme').on('click.jstree', function (ev, data) {
    return false;
  });

  $('select.judgment').on('click.jstree', function (ev, data) {
    return false;
  });
}

function redraw(jstree) { // redraw([jstree])

  var timer = new Timer();
  timer.start();

  console.log('redraw: start!');

  if (!jstree) {
    jstree = get_jstree()
  }

  jstree.redraw(true);
  reset_select_listeners();

  console.log(timer.get()+' ms for redraw');

}

function redraw_node(node, jstree, callback) { // redraw_node(node[, jstree[, callback]])

  window.requestAnimationFrame(function (timestamp) {
    console.log('redraw_node: id='+node.id);

    if (!jstree) {
      jstree = get_jstree();
    }

    jstree.redraw_node(node, false, false, false);

    if (callback) {
      callback();
    }

    console.log('redraw_node: done. ('+(window.performance.now() - timestamp)+' ms)');
  });
}

function findPos(obj) {
  var curLeft = 0;
  var curTop = 0;
  if (obj.offsetParent) {
    do {
      curLeft += obj.offsetLeft;
      curTop += obj.offsetTop;
    } while (obj = obj.offsetParent);
    return [curLeft,curTop];
  }
}

function clear_search(jstree) {
  console.log('clear_search');
  $('#count').text('');
  $('#cur').text('');
  if (!jstree) {
    jstree = get_jstree();
  }
  var nds = jstree.search_result['nodes']
  var n = nds.length, nd;
  for (var i = 0; i < n; i++) {
    nd = nds[i];
    nd.state.selected = false;
    redraw_node(nd, jstree);
  }
  jstree.search_result = {'kw':'','nodes':[],'idx':0};
}

function _expand_loops($node, key) {
  var jstree = get_jstree();
  var m = jstree._model.data;
  var i, j, parents, nd, parent;
  var nc = $node.children_d.length;
  for (i = 0; i < nc; i++) {
    nd = m[$node.children_d[i]];
    if (typeof nd.original[key] !== 'undefined') {
      if (nd.original[key]) {
        parents = nd.parents;
        var np = parents.length;
        for (j = 0; j < np; j++) {
          parent = m[parents[j]];
          parent.state.opened = true;
        }
        _expand_all(nd);
      }
    }
  }
}

function _expand_relevant_loops($node) {
  _expand_loops($node, 'relevant');
}

function _expand_target_loops($node) {
  _expand_loops($node, 'target');
}

function _change_state_all($node, opened) {
  var jstree = get_jstree();
  var m = jstree._model.data, id;
  $node.state.opened = opened;
  var nc = $node.children_d.length;
  for (var i = 0; i < nc; i++) {
    id = $node.children_d[i];
    if(m.hasOwnProperty(id) && id !== '#') {
      m[id].state.opened = opened;
    }
  }
}

function _expand_all($node) {
  _change_state_all($node, true);
}

function _collapse_all($node) {
  _change_state_all($node, false);
}

function set_node_data(d, node) {
  d['nid'] = node.id;
  d['idx'] = node.original.idx;
  d['lmi'] = node.original.lmi;
  d['path'] = node.original.loc;
  d['lnum'] = node.original.sl;

  if (!d['lnum']) {
    d['lnum'] = 0;
  }
  if (node.original.relevant) {
    d['relevant'] = true;
  }
  if (node.original.target) {
    d['target'] = true;
  }
}

function mkpost() { // mkpost([node])
  var d = {'user':USER,'proj': PROJ,'ver':VER};

  var node_data = [];

  if (arguments.length > 0) {
    var a = arguments[0];
    var nodes;

    if ($.isArray(a)) {
      nodes = a;
    } else {
      nodes = [a];
    }
    for (i in nodes) {
      var ndat = {};
      set_node_data(ndat, nodes[i]);
      node_data.push(ndat);
    }
  }

  if (node_data.length > 0) {
    d['node_data'] = JSON.stringify(node_data);
  }

  return d;
}

function post_log(rec) {
  console.log('post_log', rec);

  $.ajax({
    type: 'POST',
    url: '../cgi-bin/log',
    data: rec,
    timeout: AJAX_TIMEOUT,
    success: function (data, status, xhr) {
      if (status == 'success') {

        var count = 0;
        for (i in data.log) {
          //console.log(data.log[i]);
          count += 1;
        }

        if (count > 0)
          console.log('post_log: ['+data.time+']['+data.user+']['+data.ip+'] '+count+' logs');

        var failures = [];
        for (i in data.failure) {
          failures.push(i+':'+data.failure[i]);
        }

        if (failures.length > 0)
          alert(failures.join(', '));

      }
    },
  });

}

function get_top_node(jstree) {
  var root = jstree.get_node('#');
  var m = jstree._model.data;
  return m[root.children[0]];
}

function get_node_tbl(jstree) { // get_node_tbl([jstree])
  if (!jstree) {
    jstree = get_jstree();
  }
  return get_top_node(jstree).original.node_tbl;
}

function setup_targets(jstree) {
  var root, m, targets;
  root = jstree.get_node('#');
  m = jstree._model.data;
  targets = m[root.children[0]].original.targets;
  if (targets) {
    var nodes = targets.map(function(x){return m[x];});
    nodes.sort(function (x0, x1) {
      return cmp_lns(get_lns(m, x0), get_lns(m, x1));
    });
    //console.log(nodes);
    try {
      jstree.target_info = {'ids':nodes.map(function(x){return x.id;}),'idx':0};
    } catch (exn) {
    }
  }
}

function add_to_history(jstree, x) {
  jstree.history.unshift(x);
  if (jstree.history.length > HISTORY_SIZE) {
    jstree.history.pop();
  }
}

function recover_last_view(jstree) {
  var root, m, last_nid;
  root = jstree.get_node('#');
  m = jstree._model.data;
  last_nid = m[root.children[0]].original.last_nid;
  console.log('last_nd:', last_nid);
  if (last_nid) {
    add_to_history(jstree, last_nid);
    scrollTo(last_nid);
  }
}

function handle_search_result(jstree, kw, parents, nodes) {
  var m = jstree._model.data;
  var count = nodes.length;

  if (count == 0) {
    $('#count').text(0);

  } else if (count > 0) {

    var need_to_redraw = [];

    parents = $.vakata.array_unique(parents);

    for (var i = 0; i < parents.length; i++) {
      parent = m[parents[i]];
      if (!parent.state.opened && parent.id !== '#') {
        parent.state.opened = true;
        need_to_redraw.push(parent);
      }
    }

    $('#count').text(count);
    console.log('hits:', count);

    console.log('need_to_redraw:', need_to_redraw.length);

    for (var i = 0; i < need_to_redraw.length; i++) {
      //console.log(need_to_redraw[i]);
      redraw_node(need_to_redraw[i], jstree);
    }
    for (var i = 0; i < nodes.length; i++) {
      redraw_node(nodes[i], jstree);
    }

    //console.log(nodes);

    nodes.sort(function (x0, x1) {
      return cmp_lns(get_lns(m, x0), get_lns(m, x1));
    });

    //console.log(nodes.map(function(x){return get_lns(m, x).join();}));

    jstree.search_result = {'kw':kw,'nodes':nodes,'idx':0};

    var id0 = nodes[0].id;
    console.log('id0:', id0);

    window.requestAnimationFrame(function (timestamp) {
      var elem = document.getElementById(id0);
      if (elem) {
        scrollTo(id0);
        set_cur(0);
      }
    });

  }
}

function jump_to_callee(node) {
  if (node.children.length == 0) {
    var jstree, callee_name, callees;
    jstree = get_jstree();
    clear_search(jstree);
    if (jstree.callees_tbl) {
      callee_name = node.original.callee;
      callees = jstree.callees_tbl[callee_name];
      console.log('callees: '+callee_name+' -> ',callees);
      if (callees) {
        add_to_history(jstree, node.id);
        var nodes = [], nd, parents = [];
        for (var i in callees) {
          nd = jstree.get_node(callees[i]);
          nodes.push(nd);
          nd.state.selected = true;
          parents = parents.concat(nd.parents);
        }
        handle_search_result(jstree, '', parents, nodes);
      }
    }
  }
}

function jump_to_callee_or(node, open_source) {
  if (node.children.length == 0) {
    var jstree, callee_name, callees;
    jstree = get_jstree();
    clear_search(jstree);
    callee_name = node.original.callee;
    if (jstree.callees_tbl) {
      callees = jstree.callees_tbl[callee_name];
    }
    console.log('callees: '+callee_name+' -> ',callees);
    if (callees) {
      var dialog = $('#dialog').dialog('option', {
        autoOpen : true,
        title    : 'Jump or open?',
        width    : 350,
        buttons  : {
          'Jump to callee': function () {
            $(this).dialog('close');
            add_to_history(jstree, node.id);
            var nodes = [], nd, parents = [];
            for (var i in callees) {
              nd = jstree.get_node(callees[i]);
              nodes.push(nd);
              nd.state.selected = true;
              parents = parents.concat(nd.parents);
            }
            handle_search_result(jstree, '', parents, nodes);
            //$(this).dialog('destroy');
          },
          'Open source' : function () {
            $(this).dialog('close');
            open_source();
            //$(this).dialog('destroy');
          },
          Cancel: function () {
            $(this).dialog('close');
            //$(this).dialog('destroy');
          }
        },
      });
      var mes = '<p>';
      mes += '<span class="ui-icon ui-icon-alert"';
      mes += ' style="float:left;margin:3px 7px 50px 0;"></span>';
      mes += 'You can jump to a <b>'+callee_name+'</b>.<br>';
      mes += 'Jump to the callee or open the source?';
      mes += '</p>';

      set_dialog_message(mes);
      dialog.dialog('open');

    } else {
      open_source();
    }
  } else {
    open_source();
  }
}

function put_target_mark(node) {
  node.text = node.text.replace('class="node"', 'class="target_node"');
}

function put_completed_mark(node) {
  node.text = node.text.replace('class="target_node"', 'class="target_node_completed"');
}

function remove_completed_mark(node) {
  node.text = node.text.replace('class="target_node_completed"', 'class="target_node"');
}

function is_relevant(node) {
  var b = false;
  if (node.original) {
    b = node.original.relevant;
  }
  return b;
}

function set_judgment(node, judgment) {

  var x = ['value="',judgment,'"'].join('');
  var text = node.text.replace(' selected', '').replace(x, x+' selected');
  node.text = text;

  //console.log(node);
}

function handle_judgment(node, node_tbl, jstree, m, judgment) {
  var base_nodes;

  //console.log('handle_judgment', node);

  if (jstree.is_checked(node)) {
    var checked_nodes = jstree.get_checked(true);
    base_nodes = checked_nodes.filter(function(nd){return is_relevant(nd) && nd != node;});
    base_nodes.push(node);

  } else {
    base_nodes = [node];
  }

  //console.log(base_nodes);

  var nids = [];

  for (var bi in base_nodes) {
    var nd = base_nodes[bi];
    var lnum = nd.original.sl.toString();
    var nids0;
    try {
      nids0 = node_tbl[nd.original.loc][lnum];
    } catch (exn) {
    }

    if (!nids0)
      nids0 = [];

    nids.push(nd.id);

    if (nids0.length > 0) {
      for (var i in nids0) {
        if (nids0[i] in m && $.inArray(nids0[i], nids) == -1) {
          nids.push(nids0[i]);
        }
      }
    }
  }

  var nodes = nids.map(function(i){return m[i];});

  //console.log(nodes);

  var not_completed = judgment == 'NotYet';

  for (var i in nodes) {
    set_judgment(nodes[i], judgment);
    if (not_completed) {
      remove_completed_mark(nodes[i]);
    } else {
      put_completed_mark(nodes[i]);
    }
  }

  return nodes;
}

function get_link(obj, vkind, vid, algo, meth) {
  var url;
  if (vkind == 'GITREV') {

    url = ['/gitweb/?p=',PID,';a=blob_plain;f=',obj.loc,';h=',obj.fid,';hb=',vid].join('');
  } else {
    url = ['projects/',PROJ,'/',vid,'/',obj.loc].join('');
  }

  var params = {
    'proj' : PROJ,
    'algo' : algo,
    'meth' : meth,
    'path' : obj.loc,
    'ver'  : VER,
    'src'  : url,
  }

  if (obj.sl && obj.el) {
    params['startl'] = obj.sl;
    params['endl'] = obj.el;
  }

  var head = true;
  var l = ['openviewer?']
  for (var pname in params) {
    l.push((head ? '' : '&')+pname+'='+encodeURIComponent(params[pname]));
    head = false;
  }

  var link = l.join('');

  return link;
}

function is_visible(m, node) {
  var parents = node.parents;
  var parent, visible = true;
  for (i in parents) {
    parent = m[parents[i]];
    if (parent.state.opened == false) {
      visible = false;
      break;
    }
  }
  return visible;
}

function j_sel_on_change(ev, ui) {
  var j = ui.item.value;
  var li = $(ev.target).closest('li');
  var jstree = get_jstree();
  var m = jstree._model.data;
  var nd = m[li[0].id];
  var node_tbl = get_node_tbl(jstree);

  var nds = handle_judgment(nd, node_tbl, m, j);

  //redraw(jstree);

  var n_visible_nodes = 0;
  for (var i in nds) {
    if (is_visible(m, nds[i])) {
      redraw_node(nds[i], jstree);
      n_visible_nodes += 1;
    }
  }
  console.log(n_visible_nodes+' visible nodes redrawn');

  var d = mkpost(nds);
  d['judgment'] = j;
  post_log(d);
}

function handle_estimation_scheme(node, prev_lv, lv) {
  //console.log('handle_estimation_scheme', prev_lv, '->', lv);

  var prev_lv_id = make_lv_id(node.id, prev_lv);
  var lv_id = make_lv_id(node.id, lv);

  var prev = ['class="on_level ',prev_lv_id,'"'].join('');
  var curr = ['class="on_level ',lv_id,'"'].join('');

  var prev0 = prev+' style="display:inline;"';
  var curr1 = curr+' style="display:inline;"';

  console.log(prev0, '->', prev);
  console.log(curr, '->', curr1);

  var x = ['value="', lv, '"'].join('');
  node.text = 
    node.text.replace(['prev="',prev_lv,'"'].join(''), ['prev="',lv,'"'].join(''))
    .replace(new RegExp(prev0, 'g'), prev).replace(new RegExp(curr, 'g'), curr1)
    .replace(' selected', '').replace(x, x+' selected');

}

function make_lv_id(id, lv) {
  var lv_id = id + 'lv' + lv.toString();
  return lv_id;
}


$('#progressbar').progressbar({
  value: false,
  change: function (ev, ui) {
    var max = $('#progressbar').progressbar('option', 'max');
    var value = $('#progressbar').progressbar('value');
    var progress = Math.ceil(value * 100 / max);
    $('.progressbar-label').text(progress+'%');
  },
  complete: function (ev, ui) {
    $('.progressbar-label').text('Completed!');
  },
});

function show_progressbar() {
  $('#progressbar').css('display', 'block');
}

function hide_progressbar() {
  $('#progressbar').css('display', 'none');
}


function cmp_lns(lns0, lns1) {
  var len0 = lns0.length;
  var len1 = lns1.length;

  var min = Math.min(len0, len1);

  for (var i = 0; i < min; i++) {
    if (lns0[i] > lns1[i]) return 1;
    if (lns0[i] < lns1[i]) return -1;
  }
  if (len0 > len1) return 1;
  if (len0 < len1) return -1;

  return 0;
}

function get_lns(mdata, node) {
  var lns = [node.original.sl], ps = node.parents, pid, po, pinfo;
  var cur = (node.original.loc, node.original.pu);
  for (var i in ps) {
    pid = ps[i];
    if (pid != '#') {
      po = mdata[pid].original;
      pinfo = (po.loc, po.pu);
      if (pinfo != cur) {
        cur = pinfo;
        lns.splice(0, 0, parseInt(po.sl));
      }
    }
  }
  return lns;
}

function expand_all(node) {
  console.log('expand_all');
  _expand_all(node);
  redraw(get_jstree());

  var d = mkpost(node);
  d[EXPAND_ALL] = true;
  post_log(d);
}

function make_comment_id(nid) {
  return 'c_'+nid;
}

function make_comment_icon(nid) {
  var cid = make_comment_id(nid)
  return '<i class="jstree-icon comment-icon" id="'+cid+'" role="presentation"></i>';
}

function set_comment(node) {
  var comment = $('#comment');
  comment.removeClass('ui-state-error');

  var c = comment.val();
  console.log('set_comment:', node.id, c);
  //console.log(node);

  if (c == '') {
    var cid = make_comment_id(node.id);
    //console.log('removing "'+cid+'"');
    $('#'+cid).remove();
    var new_text = node.text.replace(new RegExp('<i .+'+cid+'.+</i>'), '');
    //console.log(new_text);
    node.text = new_text;
  } else {
    var icon = make_comment_icon(node.id);
    if (node.text.indexOf('comment-icon') < 0) {
      node.text = node.text + icon;
    }
  }
  node.a_attr.title = c;

  redraw_node(node);
  $('#dialog').dialog('close');

  var d = mkpost(node);
  d['comment'] = c;
  d['has_comment'] = c != '';
  post_log(d);
}

function set_dialog_message(mes) {
  $('#message').remove();
  var s = '<div id="message">'+mes+'</div>';
  $(s).appendTo('#dialog');
}

function set_cur(idx) {
  $('#cur').text((idx+1)+' /');
}

function jump_to_prev() {
  console.log('jump_to_prev');
  var jstree = get_jstree();

  if (jstree.search_result) {
    var idx = jstree.search_result['idx'] - 1;
    var nds = jstree.search_result['nodes'];

    if (nds.length > 0) {
      if (idx < 0) {
        idx = nds.length - 1;
      }
      //console.log(idx, nds[idx].original.code);

      jstree.search_result['idx'] = idx;
      var elem = document.getElementById(nds[idx].id);
      if (elem) {
        scrollTo(nds[idx].id);
        set_cur(idx);
      }
    }
  }
}

function jump_to_next() {
  console.log('jump_to_next');
  var jstree = get_jstree();

  if (jstree.search_result) {

    var nds = jstree.search_result['nodes'];

    if (nds.length > 0) {

      var idx = jstree.search_result['idx'] + 1;

      if (idx >= nds.length) {
        idx = 0;
      }
      //console.log(idx, nds[idx].original.code);

      jstree.search_result['idx'] = idx;
      var elem = document.getElementById(nds[idx].id);
      if (elem) {
        scrollTo(nds[idx].id);
        set_cur(idx);
      }
    }
  }
}

function jump_to_comment() {
  var sel = $('#comments');
  sel.removeClass('ui-state-error');
  var comments = sel.val();
  if (comments) {
    var jstree = get_jstree();
    var nodes = [], nd, parents = [];
    for (var i in comments) {
      var j = comments[i];
      if (j) {
        nd = jstree.get_node(comments[i]);
        nodes.push(nd);
        nd.state.selected = true;
        parents = parents.concat(nd.parents);
      }
    }
    handle_search_result(jstree, '', parents, nodes);
  }
  $('#dialog').dialog('close');
}

function list_comments() {
  var jstree = get_jstree();
  var root = jstree.get_node('#');
  var m = jstree._model.data;
  var comments = [];

  $.each(root.children_d, function (ii, i) {
    node = m[i];
    if (node.a_attr.title) {
      //console.log(node.a_attr.title);
      comments.unshift([node.a_attr.title, i]);
    }
  });

  var ncomments = comments.length

  if (ncomments == 0)
    return;

  var form;

  var dialog = $('#dialog').dialog('option', {
    autoOpen : true,
    width   : 400,
    title   : 'Comment list',
    buttons : {
      "Jump": function () {
        jump_to_comment();
      },
      Cancel: function () {
        $(this).dialog('close');
        //$(this).dialog('destroy');
      },
    },
    close: function () {
      form[0].reset();
      $('#comments').removeClass('ui-state-error');
    },
  });

  var sz = ncomments > MAX_COMMENT_LIST_SIZE ? MAX_COMMENT_LIST_SIZE : ncomments;
  sz++;

  var mes = '<p>';
  mes += '<form>';
  mes += '<select multiple name="comments" id="comments" size='+sz+' style="width:370px;">';
  mes += '<option value="">Select comment(s)</option>'
  for (var i in comments) {
    mes += '<option value="'+comments[i][1]+'">'+comments[i][0]+'</option>';
  }
  mes += '</select>';
  mes += '<input type="submit" tabindex="-1" style="position:absolute; top:-1000px>';
  mes += '</form>';
  mes += '</p>';

  set_dialog_message(mes);

  form = dialog.find("form").on("submit", function(event) {
    event.preventDefault();
    jump_to_comment();
  });

  dialog.dialog('open');

}


function treeview(data_url, vkind, vid, algo, meth) {
  global_timer.start();

  $('#outline').on('open_node.jstree', function (ev, data) {
    console.log('open_node');

    //attach_ui();

    var d = mkpost(data.node);
    d['opened'] = true;
    post_log(d);

  }).on('close_node.jstree', function (ev, data) {
    console.log('close_node');
    var d = mkpost(data.node);
    d['opened'] = false;
    post_log(d);

  }).on('loaded.jstree', function (ev, data) {
    console.log('loaded ('+global_timer.get()+')');

  }).on('redraw.jstree', function (ev, data) {
    console.log(data.nodes.length+' nodes redrawn ('+global_timer.get()+')');

  }).on('ready.jstree', function (ev, data) {
    console.log('ready ('+global_timer.get()+')');

    reset_select_listeners();

    var jstree = data.instance;

    // for checkbox and callees_tbl
    var root = jstree.get_node('#');
    var mdata = jstree._model.data;
    jstree.callees_tbl = mdata[root.children[0]].original.callees_tbl;
    var node, o, count = 0;
    for (var nid in mdata) {
      count += 1
      node = mdata[nid];
      o = node.original;
      if (o) {
        if (o.checked) {
          jstree.check_node(node);
        }
      }
    }

    setup_targets(jstree);

    console.log(count+' nodes initialized ('+global_timer.get()+')');

    jstree.nnodes = count;

    jstree.history = [];

    recover_last_view(jstree);

  }).jstree({

    "core" : {
      "data" : {
        "url" : data_url,
        "dataType" : "json"
      },
      "dblclick_toggle" : false,
      "worker" : false,
    },

    "types" : {
      "default" : {
        "icon" : ICONS_DIR+"/default.gif",
      },
      "file" : {
        "icon" : ICONS_DIR+"/file.gif",
      },
      "part" : {
        "icon" : ICONS_DIR+"/part.gif",
      },
      "block" : {
        "icon" : ICONS_DIR+"/block.gif",
      },
      "loop" : {
        "icon" : ICONS_DIR+"/do.gif",
      },
      "branch" : {
        "icon" : ICONS_DIR+"/if.gif",
      },
      "call" : {
        "icon" : ICONS_DIR+"/call.gif",
      },
      "main" : {
        "icon" : ICONS_DIR+"/mainprogram.gif",
      },
      "subroutine" : {
        "icon" : ICONS_DIR+"/subroutine.gif",
      },
      "function" : {
        "icon" : ICONS_DIR+"/function.gif",
      },
      "mpi" : {
        "icon" : ICONS_DIR+"/mpi.gif",
      },
      "omp" : {
        "icon" : ICONS_DIR+"/omp.gif",
      },
      "acc" : {
        "icon" : ICONS_DIR+"/acc.gif",
      },
      "ocl" : {
        "icon" : ICONS_DIR+"/fujitsu.gif",
      },
      "dec" : {
        "icon" : ICONS_DIR+"/intel.gif",
      },
      "xlf" : {
        "icon" : ICONS_DIR+"/ibm.gif",
      },
      "pp" : {
        "icon" : ICONS_DIR+"/pp_directive.gif",
      },
      "call*" : {
        "icon" : ICONS_DIR+"/call_null.gif",
      },
    },

    "conditionalselect" : function (node, event) {
      //console.log('activated ', node);

      var c = event.target.getAttribute('class');

      if (c == 'jstree-icon jstree-checkbox') {
        //console.log('check');
        var d = mkpost(node);
        var jstree = get_jstree();
        if (jstree.is_checked(node)) {
          jstree.uncheck_node(node);
          d['checked'] = false;
        } else {
          jstree.check_node(node);
          d['checked'] = true;
        }
        post_log(d);
      }

      return false;
    },

    "checkbox" : {
      "tie_selection" : false,
      "whole_node"    : false,
    },

    "contextmenu" : {
      "select_node" : false,
      "items"       : function ($node) {
        return {
          "open_source" : {
            "label"  : "Open Source",
            "icon"   : ICONS_DIR+"/openfile.gif",
            "action" : function (obj) {

              var form = document['form_'+$node.id];
              //console.log('form', form);
              if (form) {
                form.submit();
              }
              var d = mkpost($node);
              d['open_source'] = true;
              post_log(d);
            },
          },
          "set_comment" : {
            "label" : "Add/Modify Comment",
            "icon"  : ICONS_DIR+"/Bubble.png",
            "action" : function (obj) {

              var form;

              var dialog = $('#dialog').dialog('option', {
                autoOpen : true,
                width   : 400,
                title   : 'Add comment',
                buttons : {
                  "Submit": function () {
                    set_comment($node);
                  },
                  "Clear": function () {
                    $('#comment').text('');
                  },
                  Cancel: function () {
                    $(this).dialog('close');
                    //$(this).dialog('destroy');
                  },
                },
                close: function () {
                  form[0].reset();
                  $('#comment').removeClass('ui-state-error');
                },
              });

              var mes = '<p>';
              mes += '<form>';
              mes += '<textarea name="comment" id="comment" style="width:100%;">';
              mes += '</textarea>';
              mes += '<input type="submit" tabindex="-1" style="position:absolute; top:-1000px>';
              mes += '</form>';
              mes += '</p>';

              set_dialog_message(mes);

              form = dialog.find("form").on("submit", function(event) {
                event.preventDefault();
                set_comment($node);
              });

              dialog.dialog('open');

              var c = $node.a_attr.title;
              if (c)
                $('#comment').text(c);
            },
          },
          "list_comments" : {
            "label" : "List Comments",
            "icon"  : ICONS_DIR+"/Bubble.png",
            "action" : function (obj) {
              list_comments();
            },
          },
          EXPAND_TARGET_LOOPS : {
            "label"  : "Expand Target Loops",
            "icon"   : ICONS_DIR+"/expandall.gif",
            "action" : function (obj) {

              var nnodes = $node.children_d.length;

              if (nnodes == 0)
                return;
              
              console.log('expand_target_loops');
              _expand_target_loops($node);
              redraw(get_jstree());

              var d = mkpost($node);
              d[EXPAND_TARGET_LOOPS] = true;
              post_log(d);

            },
          },
          EXPAND_RELEVANT_LOOPS : {
            "label"  : "Expand Relevant Loops",
            "icon"   : ICONS_DIR+"/expandall.gif",
            "action" : function (obj) {

              var nnodes = $node.children_d.length;

              if (nnodes == 0)
                return;
              
              console.log('expand_relevant_loops');
              _expand_relevant_loops($node);
              redraw(get_jstree());

              var d = mkpost($node);
              d[EXPAND_RELEVANT_LOOPS] = true;
              post_log(d);

            },
          },
          EXPAND_ALL : {
            "label"  : "Expand All",
            "icon"   : ICONS_DIR+"/expandall.gif",
            "action" : function (obj) {
              //$.jstree.reference('#outline').open_all($node);

              var nnodes = $node.children_d.length;

              if (nnodes == 0)
                return;

              if (nnodes > 512) {

                var dialog = $('#dialog').dialog('option', {
                  autoOpen : true,
                  title   : 'Expand all?',
                  width   : 350,
                  buttons : {
                    'Ok': function () {
                      $(this).dialog('close');

                      expand_all($node);

                      //$(this).dialog('destroy');
                    },
                    Cancel: function () {
                      $(this).dialog('close');
                      //$(this).dialog('destroy');
                    }
                  },
                });

                var mes = '<p>';
                mes += '<span class="ui-icon ui-icon-alert"';
                mes += ' style="float:left;margin:3px 7px 50px 0;"></span>';
                mes += 'Do you really want to expand <b>'+nnodes+'</b> nodes?';
                mes += '</p>';

                set_dialog_message(mes);

                dialog.dialog('open');

                //ok = confirm('Do you really want to expand '+nnodes+' nodes?');

              } else {
                expand_all($node);
              }

            }
          },
          COLLAPSE_ALL : {
            "label"  : "Collapse All",
            "icon"   : ICONS_DIR+"/collapseall.gif",
            "action" : function (obj) {
              //$.jstree.reference('#outline').close_all($node);

              console.log('collapse_all');
              _collapse_all($node);
              redraw(get_jstree());

              var d = mkpost($node);
              d[COLLAPSE_ALL] = true;
              post_log(d);

            },
          },
          "back" : {
            "label"  : "Back",
            "icon"   : ICONS_DIR+"/backward.gif",
            "action" : function (obj) {
              var jstree = get_jstree();
              console.log('history:', jstree.history);
              scrollTo(jstree.history[0]);
            },
          },
          "open_text_view" : {
            "label"  : "Open Text View",
            "icon"   : ICONS_DIR+"/openfile.gif",
            "action" : function (obj) {
              try {
                var url = 'texttree?' + data_url.split('?')[1];
                console.log('opening '+url);
                window.open().location.href = url;
              } catch (exn) {
              }
            },
          },
        };
      }
    },

    "plugins" : [ "types", "contextmenu", "checkbox", "conditionalselect" ],

  }).bind('dblclick.jstree', function (ev, data) {
    if (ev.target) {
      var nd = get_target_node(ev);

      if (ev.target.classList.contains('link-icon')) {
        jump_to_callee(nd);
      } else {
        function open_source() {
          var form = document['form_'+nd.id];
          if (form) {
            form.submit();
          }
          var d = mkpost(nd);
          d['open_source'] = true;
          post_log(d);
        }
        jump_to_callee_or(nd, open_source);
      }

    }
  }).bind('change', function (ev, data) {
    console.log('change: ev.target=', ev.target);

    var sel = $(ev.target);
    var nd = get_target_node(ev);
    var jstree = get_jstree();

    switch (ev.target.className) {
    case 'estimation-scheme':
      var prev_lv = sel.attr('prev');
      var lv = sel.val();

      console.log('prev_lv=',prev_lv);
      console.log('lv=',lv);

      handle_estimation_scheme(nd, prev_lv, lv);

      redraw_node(nd, jstree, function () {
        $('#es_'+nd.id).on('click.jstree', function (ev, data) {
          console.log('resetting handler for estimation-scheme');
          return false;
        });
        $('#j_'+nd.id).on('click.jstree', function (ev, data) {
          console.log('resetting handler for judgment');
          return false;
        });
      });

      var d = mkpost(nd);
      d['estimation_scheme'] = lv;
      post_log(d);

      break;

    case 'judgment':
      var j = sel.val();
      var node_tbl = get_node_tbl(jstree);
      var m = jstree._model.data;

      var nds = handle_judgment(nd, node_tbl, jstree, m, j);

      var n_visible_nodes = 0, ni;
      for (var i in nds) {
        ni = nds[i];
        if (is_visible(m, ni)) {
          redraw_node(ni, jstree, function () {
            $('#es_'+ni.id).on('click.jstree', function (ev, data) {
              console.log('resetting handler for estimation-scheme');
              return false;
            });
            $('#j_'+ni.id).on('click.jstree', function (ev, data) {
              console.log('resetting handler for judgment');
              return false;
            });
          });
          n_visible_nodes += 1;
        }
      }
      console.log(n_visible_nodes+' visible nodes redrawn');

      var d = mkpost(nds);
      d['judgment'] = j;
      post_log(d);

      break;
    }

  });

  var to = false;

  function search() {
    var data_source = $('#datasrc').val();

    console.log('search: '+data_source);

    if (to) {
      clearTimeout(to);
    }
    to = setTimeout(function () {

      var jstree = get_jstree();
      console.log('search result:', jstree.search_result);
      var kw = $('#search').val().toLowerCase();

      if (kw == '') {
        clear_search(jstree);
        return;

      } else {
        var prev_kw = jstree.search_result['kw'];
        if (kw == prev_kw) {
          var idx = jstree.search_result['idx'] + 1;
          var nds = jstree.search_result['nodes'];

          if (idx >= nds.length) {
            idx = 0;
          }
          //console.log(idx, nds[idx].original.code);

          jstree.search_result['idx'] = idx;
          var elem = document.getElementById(nds[idx].id);
          if (elem) {
            //elem.scrollIntoView();
            scrollTo(nds[idx].id);
          }
          return;

        } else {
          clear_search(jstree);
        }
      }
      console.log('searching for "%s"', kw);

      var d = mkpost();
      d['search'] = kw;
      d['datasrc'] = data_source;
      post_log(d)

      //$('#outline').jstree(true).search(kw, true);

      var nodes = [];
      var root = jstree.get_node('#');
      var m = jstree._model.data;
      var parents = [], node, parent;

      var search_comment = data_source == COMMENT;
      var search_code = data_source == CODE;

      if (data_source == ALL) {
        search_comment = true;
        search_code = true;
      }

      $.each(root.children_d, function (ii, i) {
        node = m[i];

        hit = false;

        if (node.original.code && search_code) {
          if (node.original.code.toLowerCase().includes(kw)) {
            hit = true;
          }
        }
        if (node.a_attr.title && search_comment) {
          if (node.a_attr.title.toLowerCase().includes(kw)) {
            hit = true;
          }
        }

        if (hit) {
          node.state.selected = true;
          nodes.push(node);
          parents = parents.concat(node.parents);
        }

      });

      handle_search_result(jstree, kw, parents, nodes);

    }, 200);

  }

  $('#search').keypress(function (ev) {
    if (ev.which == 13) {
      $('#search').blur();
      search();
    }
  });

  $('#goButton').on('click', function (ev) {
    if (safari) {
      $(ev.target).css('background-color', go_button_bg);
    }
    console.log('goButton: click');
    search();
  });

  $('#datasrc').on('change', function () {
    var datasrc = $('#datasrc').val();
    console.log('datasrc: change: '+datasrc);
    var kw = $('#search').val();
    if (kw) {
      clear_search();
      search();
    }
  });


  get_jstree().search_result = {'kw':'','nodes':[],'idx':0};

  $('#clearButton').on('click', function (ev) {
    if (safari) {
      $(ev.target).css('background-color', clear_button_bg);
    }
    console.log('clearButton: click');
    $('#search').val('');

    //$('#outline').jstree(true).clear_search();
    //$('#outline').jstree(true).deselect_all();

    clear_search();

  });

  $('#prevButton').on('click', function (ev) {
    if (safari) {
      $(ev.target).css('background-color', prev_button_bg);
    }
    console.log('prevButton: click');
    jump_to_prev();
  });

  $('#nextButton').on('click', function (ev) {
    if (safari) {
      $(ev.target).css('background-color', next_button_bg);
    }
    console.log('nextButton: click');
    jump_to_next();
  });

  $('#kernelButton').on('click', function (ev) {
    if (safari) {
      $(ev.target).css('background-color', target_button_bg);
    }
    var jstree = get_jstree();
    if (jstree.target_info) {
      var nodes = [], node, parents = [];
      //var idx = jstree.target_info['idx'];
      var ids = jstree.target_info['ids'];
      for (var i in ids) {
        var elem = document.getElementById(ids[i]);
        if (elem) {
          node = jstree.get_node(ids[i]);
          nodes.push(node);
          //node.state.selected = true;
          parents = parents.concat(node.parents);
        }
      }
      handle_search_result(jstree, '', parents, nodes);
/*
      var elem = document.getElementById(ids[idx]);
      if (elem)
        scrollTo(ids[idx]);

      if (idx >= (ids.length - 1)) {
        jstree.target_info.idx = 0;
      } else {
        jstree.target_info.idx += 1;
      }
*/
    }
  });

  var sp = $('#searchPanel');
  var spTop = sp.offset().top;
  $(window).scroll(function () {
    var winTop = $(this).scrollTop();
    if (winTop >= spTop) {
      sp.addClass('fixed').css('top',0);
    } else if (winTop < spTop) {
      sp.removeClass('fixed').css('top',-spTop+'px');
    }
  });

  $('#dialog').dialog({
    autoOpen : false,
    modal    : true,
    position : {
      my: "center",
      at: "center",
      using: function (pos, feedback) {
        var h = get_window_height();
        $(this).css({position:'fixed',top:h/2,left:pos.left});
      },
    },
  });


  $(document)/*.on('mouseover', function (ev) {

    var mes;

    switch (ev.target.className) {
    case 'metrics':
      switch (ev.target.firstChild.data) {
      case 'FOp':
        mes = 'number of floating-point operations';
        break;
      case 'St':
        mes = 'number of statements';
        break;
      case 'Br':
        mes = 'number of branch statements';
        break;
      case 'AR0':
      case 'AR1':
      case 'AR2':
        mes = 'number of array references';
        break;
      case 'DAR0':
      case 'DAR1':
      case 'DAR2':
        mes = 'number of double array references';
        break;
      case 'IAR0':
      case 'IAR1':
      case 'IAR2':
        mes = 'number of indirect array references';
        break;
      default:
        break;
      }
      break;
    case 'es':
      mes = 'estimation scheme';
      break;
    default:
      break;
    }
    if (mes) {
      $(ev.target).prop('title', mes);
    }

  })*/.tooltip({
      position: {
        my: "center bottom-20",
        at: "center top",
        using: function(position, feedback) {
          $(this).css(position);
          /*
          $("<div>")
            .addClass("arrow")
            .addClass(feedback.vertical)
            .addClass(feedback.horizontal)
            .appendTo(this);
          */
        }
      },
      items: "[title]",
      /*content: function() {
        if ($(this).is("[title]")) {
          return $(this).attr("title");
        }
      },*/
      show: null,
      close: function(ev, ui) {
        ui.tooltip.hover(
          function() {
            $(this).stop(true).fadeTo(400, 1);
          },
          function() {
            $(this).fadeOut('400', function(){$(this).remove()});
          }
        );
      }
    });

} // end of function treeview
