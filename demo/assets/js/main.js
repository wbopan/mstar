/* ============================================================
   main — orchestration (Materialize tabs + viz coordination)
   ============================================================ */
(function () {
  Figure2.init();
  Inspector.init();

  let fig1Ready = false;
  Figure1.init().then(() => {
    fig1Ready = true;
    Figure2.setOnRound(() => Figure1.growNext());
    if (isLoopVisible()) startLoop();
  }).catch(err => console.error('Figure1', err));

  function panelVisible(id) {
    const el = document.getElementById(id);
    return el && getComputedStyle(el).display !== 'none';
  }
  function isLoopVisible() { return panelVisible('tab-loop'); }

  function startLoop() {
    if (fig1Ready) Figure1.beginGrowth();
    Figure2.reset();
    Figure2.play();
  }

  function onShow(panel) {
    if (!panel) return;
    if (panel.id === 'tab-loop') startLoop();
    else Figure2.stop();
    if (panel.id === 'tab-inspect') Inspector.onResize();
  }

  if (window.M && document.getElementById('main-tabs')) {
    M.Tabs.init(document.getElementById('main-tabs'), { onShow });
  }

  document.getElementById('loop-play').addEventListener('click', () => Figure2.togglePlay());
  document.getElementById('loop-step').addEventListener('click', () => Figure2.step());

  let rt;
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => Inspector.onResize(), 180); });
})();
