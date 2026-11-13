(function(){
  // ---------- page fade-in ----------
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.page.fade-in').forEach(function(el){
      el.style.opacity = 0;
      requestAnimationFrame(function(){
        el.style.transition = 'opacity .35s ease';
        el.style.opacity = 1;
      });
    });
  });

  // ---------- live stock polling ----------
  function refreshStock(){
    var el = document.getElementById('stockCount');
    if(!el) return;
    fetch('/api/live-stock', {credentials:'same-origin'})
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if(!d) return;
        var cur = parseInt(el.textContent, 10) || 0;
        if(d.total !== cur){
          el.classList.add('pulse');
          el.textContent = d.total;
          setTimeout(function(){ el.classList.remove('pulse'); }, 1400);
        }
      }).catch(function(){});
  }
  if(document.getElementById('stockCount')){
    refreshStock();
    setInterval(refreshStock, 15000);
  }

  // ---------- close mobile nav on link click ----------
  document.addEventListener('click', function(e){
    if(e.target.closest('.nav-links a')) document.body.classList.remove('nav-open');
  });

  // ---------- smooth internal link fades ----------
  document.querySelectorAll('a[href^="/"]:not([target])').forEach(function(a){
    a.addEventListener('click', function(ev){
      if(ev.metaKey||ev.ctrlKey||ev.shiftKey) return;
      var page = document.querySelector('.page.fade-in');
      if(!page) return;
      var href = a.getAttribute('href');
      if(href.startsWith('#')) return;
      ev.preventDefault();
      page.style.transition = 'opacity .22s ease';
      page.style.opacity = 0;
      setTimeout(function(){ window.location = href; }, 220);
    });
  });

  // ---------- banner video autoplay nudge ----------
  document.querySelectorAll('.banner-media video').forEach(function(v){
    v.muted = true;
    v.playsInline = true;
    var p = v.play();
    if(p && typeof p.catch === 'function'){ p.catch(function(){}); }
  });

  // ---------- banner preview auto-refresh on file pick ----------
  document.querySelectorAll('input[type=file]').forEach(function(inp){
    inp.addEventListener('change', function(){
      var f = inp.files && inp.files[0];
      if(!f) return;
      var card = inp.closest('.banner-edit-card');
      if(!card) return;
      var prev = card.querySelector('.banner-preview');
      if(!prev){
        prev = document.createElement('div');
        prev.className = 'banner-preview';
        prev.innerHTML = '<span class="muted small">New preview:</span>';
        card.appendChild(prev);
      }
      var url = URL.createObjectURL(f);
      var el;
      if(/\.(mp4|webm)$/i.test(f.name)){
        el = document.createElement('video');
        el.autoplay = true; el.muted = true; el.loop = true; el.playsInline = true;
      } else {
        el = document.createElement('img');
      }
      el.src = url;
      var old = prev.querySelector('img,video');
      if(old) old.remove();
      prev.appendChild(el);
    });
  });
})();