(() => {
  "use strict";

  const $ = (selector, scope = document) => scope.querySelector(selector);
  const $$ = (selector, scope = document) => [...scope.querySelectorAll(selector)];
  const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, value));

  const scanner = $("#scanner");
  const video = $("#camera");
  const preview = $("#photo-preview");
  const captureCanvas = $("#capture-canvas");
  const ctx = captureCanvas.getContext("2d", { willReadFrequently: true });
  const upload = $("#photo-upload");
  const analyzeButton = $("#analyze-photo");
  const cameraPlaceholder = $("#camera-placeholder");
  const cameraStatus = $("#camera-status");
  const IS_LOCAL = ["127.0.0.1", "localhost"].includes(location.hostname);
  const IS_STATIC_DEPLOYMENT = !IS_LOCAL;
  const API_BASE = window.DERMASCAN_API_URL
    || (location.port === "8000" ? "" : IS_LOCAL ? "http://127.0.0.1:8000" : "");
  const sessionId = getSessionId();
  let stream = null;
  let imageReady = false;
  let sourceMode = null;
  let lastAnalysis = null;
  let lastReferralToken = null;
  let userLocation = null;
  let selectedClinic = null;
  let guidanceRoute = null;

  if (IS_STATIC_DEPLOYMENT) {
    $("#deployment-banner").hidden = false;
    if (API_BASE) {
      $("#deployment-banner").textContent =
        "Aplicación conectada · Escaneo, orientación, catálogos y agenda usan el backend seguro de DermaScan.";
    }
  }

  const stages = {
    capture: $("#stage-capture"),
    processing: $("#stage-processing"),
    results: $("#stage-results"),
  };

  function showStage(name) {
    Object.entries(stages).forEach(([key, node]) => node.classList.toggle("active", key === name));
    scanner.scrollTo({ top: 0, behavior: "instant" });
  }

  function openScanner() {
    scanner.classList.add("open");
    scanner.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    showStage("capture");
    checkBackend();
  }

  function getSessionId() {
    const key = "dermascan-session";
    let value = localStorage.getItem(key);
    if (!value) {
      value = crypto.randomUUID().replaceAll("-", "");
      localStorage.setItem(key, value);
    }
    return value;
  }

  async function checkBackend() {
    try {
      const response = await fetch(`${API_BASE}/api/v1/health`);
      if (!response.ok) throw new Error("API no disponible");
      const health = await response.json();
      if (!imageReady) cameraStatus.textContent = `Motor ${health.version} conectado`;
    } catch {
      cameraStatus.textContent = IS_STATIC_DEPLOYMENT
        ? "Demo pública · análisis local disponible"
        : "Backend desconectado · inicia run_backend.ps1";
    }
  }

  function closeScanner() {
    scanner.classList.remove("open");
    scanner.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    stopCamera();
  }

  $$("[data-start-scan]").forEach((button) => button.addEventListener("click", openScanner));
  $("#close-scanner").addEventListener("click", closeScanner);
  scanner.addEventListener("click", (event) => {
    if (event.target === scanner) closeScanner();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && scanner.classList.contains("open")) closeScanner();
  });

  async function enableCamera() {
    try {
      stopCamera();
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 960 } },
        audio: false,
      });
      video.srcObject = stream;
      await video.play();
      video.style.display = "block";
      preview.style.display = "none";
      cameraPlaceholder.style.display = "none";
      cameraStatus.textContent = "Cámara activa · rostro centrado";
      sourceMode = "camera";
      imageReady = true;
      analyzeButton.disabled = false;
      setTimeout(evaluateLiveQuality, 700);
    } catch (error) {
      cameraStatus.textContent = "No fue posible acceder a la cámara";
      cameraPlaceholder.style.display = "flex";
      cameraPlaceholder.querySelector("b").textContent = "Permiso de cámara no disponible";
      cameraPlaceholder.querySelector("span").textContent = "Puedes continuar subiendo una fotografía.";
    }
  }

  function stopCamera() {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    stream = null;
    video.srcObject = null;
  }

  $("#enable-camera").addEventListener("click", enableCamera);

  upload.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 15 * 1024 * 1024) {
      cameraStatus.textContent = "La imagen supera el límite de 15 MB";
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      preview.onload = () => {
        stopCamera();
        preview.style.display = "block";
        video.style.display = "none";
        cameraPlaceholder.style.display = "none";
        cameraStatus.textContent = "Fotografía lista para evaluar";
        sourceMode = "upload";
        imageReady = true;
        analyzeButton.disabled = false;
        evaluateSourceQuality(preview);
      };
      preview.src = reader.result;
    };
    reader.readAsDataURL(file);
  });

  $("#use-demo").addEventListener("click", () => {
    const demo = document.createElement("canvas");
    demo.width = 720;
    demo.height = 900;
    const d = demo.getContext("2d");
    const bg = d.createLinearGradient(0, 0, 720, 900);
    bg.addColorStop(0, "#d7e3d2");
    bg.addColorStop(1, "#a7c1a4");
    d.fillStyle = bg;
    d.fillRect(0, 0, 720, 900);
    d.fillStyle = "#34332e";
    d.beginPath(); d.ellipse(360, 300, 210, 250, 0, 0, Math.PI * 2); d.fill();
    const skin = d.createRadialGradient(320, 350, 30, 360, 440, 260);
    skin.addColorStop(0, "#dca984");
    skin.addColorStop(1, "#a9654e");
    d.fillStyle = skin;
    d.beginPath(); d.ellipse(360, 425, 184, 248, 0, 0, Math.PI * 2); d.fill();
    d.fillStyle = "#30221d";
    d.beginPath(); d.ellipse(300, 405, 28, 10, 0, 0, Math.PI * 2); d.fill();
    d.beginPath(); d.ellipse(420, 405, 28, 10, 0, 0, Math.PI * 2); d.fill();
    d.strokeStyle = "rgba(94,48,39,.5)"; d.lineWidth = 7;
    d.beginPath(); d.moveTo(360, 420); d.quadraticCurveTo(345, 495, 375, 510); d.stroke();
    d.strokeStyle = "#7a3f40"; d.lineWidth = 8;
    d.beginPath(); d.moveTo(315, 555); d.quadraticCurveTo(360, 580, 405, 555); d.stroke();
    d.fillStyle = "#1b2923";
    d.beginPath(); d.ellipse(360, 850, 310, 225, 0, 0, Math.PI * 2); d.fill();
    [[275,510],[450,485],[295,545],[430,530]].forEach(([x,y],i)=>{
      d.fillStyle = i % 2 ? "rgba(162,57,47,.62)" : "rgba(132,52,44,.45)";
      d.beginPath(); d.arc(x,y,6+i*1.4,0,Math.PI*2); d.fill();
    });
    preview.onload = () => {
      stopCamera();
      preview.style.display = "block";
      video.style.display = "none";
      cameraPlaceholder.style.display = "none";
      cameraStatus.textContent = "Demo lista · datos ilustrativos";
      sourceMode = "demo";
      imageReady = true;
      analyzeButton.disabled = false;
      evaluateSourceQuality(preview);
    };
    preview.src = demo.toDataURL("image/jpeg", .92);
  });

  function drawSourceToCanvas(maxSize = 760) {
    const source = sourceMode === "camera" ? video : preview;
    const sw = sourceMode === "camera" ? video.videoWidth : preview.naturalWidth;
    const sh = sourceMode === "camera" ? video.videoHeight : preview.naturalHeight;
    if (!sw || !sh) throw new Error("Imagen no disponible");
    const scale = Math.min(1, maxSize / Math.max(sw, sh));
    captureCanvas.width = Math.round(sw * scale);
    captureCanvas.height = Math.round(sh * scale);
    ctx.save();
    if (sourceMode === "camera") {
      ctx.translate(captureCanvas.width, 0);
      ctx.scale(-1, 1);
    }
    ctx.drawImage(source, 0, 0, captureCanvas.width, captureCanvas.height);
    ctx.restore();
    return captureCanvas;
  }

  function calculateQuality(canvas) {
    const c = canvas.getContext("2d", { willReadFrequently: true });
    const { width, height } = canvas;
    const sample = c.getImageData(0, 0, width, height).data;
    let sum = 0, sumSq = 0, edges = 0, count = 0;
    const step = 4 * Math.max(1, Math.floor(Math.sqrt((width * height) / 90000)));
    let previous = null;
    for (let i = 0; i < sample.length; i += step) {
      const lum = .299 * sample[i] + .587 * sample[i + 1] + .114 * sample[i + 2];
      sum += lum; sumSq += lum * lum; count++;
      if (previous !== null) edges += Math.abs(lum - previous);
      previous = lum;
    }
    const brightness = sum / count;
    const contrast = Math.sqrt(Math.max(0, sumSq / count - brightness * brightness));
    const sharpness = edges / Math.max(1, count - 1);
    return {
      light: clamp(100 - Math.abs(brightness - 145) * 1.3),
      contrast: clamp(contrast * 2.35),
      sharpness: clamp(sharpness * 5.3),
      brightness,
    };
  }

  function paintQuality(quality) {
    const thresholds = { light: 52, sharpness: 38, contrast: 35 };
    Object.keys(thresholds).forEach((key) => {
      const row = $(`[data-quality="${key}"]`);
      const good = quality[key] >= thresholds[key];
      row.classList.toggle("good", good);
      row.classList.toggle("warn", !good);
      $("i", row).textContent = good ? "✓" : "!";
    });
  }

  function evaluateSourceQuality(source) {
    const temp = document.createElement("canvas");
    const max = 300;
    const scale = Math.min(1, max / Math.max(source.naturalWidth, source.naturalHeight));
    temp.width = source.naturalWidth * scale;
    temp.height = source.naturalHeight * scale;
    temp.getContext("2d").drawImage(source, 0, 0, temp.width, temp.height);
    paintQuality(calculateQuality(temp));
  }

  function evaluateLiveQuality() {
    if (!stream || !video.videoWidth) return;
    drawSourceToCanvas(300);
    paintQuality(calculateQuality(captureCanvas));
  }

  function regionStats(image, x0, y0, x1, y1) {
    const { data, width, height } = image;
    const sx = Math.floor(width * x0), ex = Math.floor(width * x1);
    const sy = Math.floor(height * y0), ey = Math.floor(height * y1);
    let n = 0, lumSum = 0, lumSq = 0, redExcess = 0, dark = 0, highlights = 0;
    let saturation = 0, gradients = 0, priorLum = null;
    for (let y = sy; y < ey; y += 2) {
      for (let x = sx; x < ex; x += 2) {
        const i = (y * width + x) * 4;
        const r = data[i], g = data[i + 1], b = data[i + 2];
        const lum = .299 * r + .587 * g + .114 * b;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        lumSum += lum; lumSq += lum * lum;
        redExcess += Math.max(0, r - (g + b) / 2);
        saturation += max ? (max - min) / max : 0;
        if (lum < 75) dark++;
        if (lum > 205 && max - min < 38) highlights++;
        if (priorLum !== null) gradients += Math.abs(lum - priorLum);
        priorLum = lum;
        n++;
      }
    }
    const mean = lumSum / n;
    return {
      mean,
      std: Math.sqrt(Math.max(0, lumSq / n - mean * mean)),
      red: redExcess / n,
      sat: saturation / n,
      darkRatio: dark / n,
      highlightRatio: highlights / n,
      gradient: gradients / Math.max(1, n - 1),
    };
  }

  function analyzeImage(canvas) {
    const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
    // The user aligns the face with the guide. Regions intentionally avoid eyes, hair and mouth.
    const forehead = regionStats(image, .34, .19, .66, .34);
    const leftCheek = regionStats(image, .25, .43, .45, .67);
    const rightCheek = regionStats(image, .55, .43, .75, .67);
    const tZone = regionStats(image, .42, .28, .58, .66);
    const eyeBand = regionStats(image, .27, .34, .73, .46);
    const face = regionStats(image, .24, .18, .76, .72);
    const cheekStd = (leftCheek.std + rightCheek.std) / 2;
    const cheekGrad = (leftCheek.gradient + rightCheek.gradient) / 2;
    const cheekRed = (leftCheek.red + rightCheek.red) / 2;
    const cheekDark = (leftCheek.darkRatio + rightCheek.darkRatio) / 2;

    const hydrationNeed = clamp((cheekStd - 18) * 2 + (cheekGrad - 8) * 2.2 + Math.max(0, 115 - face.mean) * .25);
    const oilSignal = clamp(tZone.highlightRatio * 620 + Math.max(0, tZone.mean - (leftCheek.mean + rightCheek.mean) / 2) * 1.4);
    const textureNeed = clamp((cheekGrad - 7) * 3.6 + (cheekStd - 15) * 1.5);
    const poreNeed = clamp((cheekGrad - 8) * 3.5 + cheekDark * 240 + (cheekStd - 18));
    const acneNeed = clamp((cheekRed - 8) * 5 + (face.sat - .22) * 80);
    const rednessNeed = clamp((cheekRed - 5) * 4.2);
    const pigmentationNeed = clamp(cheekDark * 300 + (cheekStd - 22) * 1.8);
    const lineNeed = clamp((eyeBand.gradient - 9) * 3.4 + (forehead.gradient - 8) * 2.1);

    const quality = calculateQuality(canvas);
    const confidence = clamp((quality.light + quality.contrast + quality.sharpness) / 3);
    const metrics = [
      metric("Hidratación", "◒", 100 - hydrationNeed, "Confort y apariencia de sequedad", hydrationNeed),
      metric("Textura", "⌁", 100 - textureNeed, "Uniformidad visual de la superficie", textureNeed),
      metric("Poros", "◌", 100 - poreNeed, "Visibilidad aparente en mejillas", poreNeed),
      metric("Imperfecciones", "·", 100 - acneNeed, "Señales rojizas compatibles con brotes", acneNeed),
      metric("Pigmentación", "◐", 100 - pigmentationNeed, "Uniformidad visible del tono", pigmentationNeed),
      metric("Líneas visibles", "≋", 100 - lineNeed, "Contrastes finos en frente y contorno", lineNeed),
      metric("Enrojecimiento", "●", 100 - rednessNeed, "Variación rojiza en mejillas", rednessNeed),
      metric("Balance sebáceo", "✦", 100 - Math.abs(oilSignal - 32) * 1.4, "Brillo aparente en la zona T", oilSignal),
    ];
    const weights = [0.15, 0.20, 0.15, 0.20, 0.15, 0.15];
    const overall = Math.round(metrics.slice(0, 6).reduce((sum, item, i) => sum + item.score * weights[i], 0));

    let skinType = "Equilibrada";
    if (oilSignal > 58 && hydrationNeed > 52) skinType = "Mixta deshidratada";
    else if (oilSignal > 58) skinType = "Grasa";
    else if (hydrationNeed > 58) skinType = "Seca";
    else if (oilSignal > 38) skinType = "Mixta";

    return { metrics, overall, skinType, confidence, needs: { hydrationNeed, oilSignal, textureNeed, poreNeed, acneNeed, rednessNeed, pigmentationNeed, lineNeed } };
  }

  function metric(name, icon, score, description, need) {
    const normalized = Math.round(clamp(score));
    return {
      name, icon, score: normalized, need: Math.round(clamp(need)), description,
      status: normalized >= 80 ? "Óptimo" : normalized >= 65 ? "Estable" : normalized >= 45 ? "Atención" : "Prioridad",
    };
  }

  analyzeButton.addEventListener("click", async () => {
    if (!imageReady) return;
    try {
      drawSourceToCanvas();
      const imageUrl = captureCanvas.toDataURL("image/jpeg", .91);
      $("#processing-image").src = imageUrl;
      $("#result-image").src = imageUrl;
      stopCamera();
      showStage("processing");
      const analysisRequest = requestAnalysis(captureCanvas);
      const phases = [
        [12, "Validando iluminación y nitidez"],
        [28, "Detectando el rostro"],
        [47, "Evaluando textura y poros"],
        [66, "Analizando tono e imperfecciones"],
        [83, "Estimando hidratación y líneas visibles"],
      ];
      for (const [progress, label] of phases) {
        await wait(280);
        $("#progress-bar").style.width = `${progress}%`;
        $("#progress-value").textContent = `${progress}%`;
        $("#processing-label").textContent = label;
      }
      const payload = await analysisRequest;
      $("#progress-bar").style.width = "100%";
      $("#progress-value").textContent = "100%";
      $("#processing-label").textContent = "Preparando tus resultados";
      lastAnalysis = payload.result;
      lastReferralToken = payload.referralToken;
      renderResults(lastAnalysis);
      await wait(260);
      showStage("results");
      requestAnimationFrame(() => drawMap(lastAnalysis));
    } catch (error) {
      showStage("capture");
      cameraStatus.textContent = error.message || "No pudimos procesar la imagen.";
    }
  });

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  function canvasBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => blob ? resolve(blob) : reject(new Error("No se pudo preparar la imagen.")),
        "image/jpeg",
        .91,
      );
    });
  }

  async function requestAnalysis(canvas) {
    const blob = await canvasBlob(canvas);
    const form = new FormData();
    form.append("image", blob, "dermascan-capture.jpg");
    form.append("save_history", $("#save-history").checked ? "true" : "false");
    let response;
    try {
      response = await fetch(`${API_BASE}/api/v1/analyze`, {
        method: "POST",
        headers: { "X-Derma-Session": sessionId },
        body: form,
      });
    } catch {
      return localFallbackAnalysis(canvas);
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      if (IS_STATIC_DEPLOYMENT && [404, 405].includes(response.status)) {
        return localFallbackAnalysis(canvas);
      }
      throw new Error(payload?.error?.message || "El backend rechazó la imagen.");
    }
    return payload;
  }

  function localFallbackAnalysis(canvas) {
    const result = analyzeImage(canvas);
    result.warnings = [
      "Resultado generado localmente en la demo pública. Las funciones conectadas al backend no están disponibles.",
    ];
    result.attentionZones = [];
    result.attentionMap = {
      derivedFromImage: false,
      coordinateSpace: "none",
      method: "static-demo-fallback",
      zoneCount: 0,
    };
    return {
      ok: true,
      referralToken: null,
      result,
      staticDemo: true,
    };
  }

  function renderResults(result) {
    $("#overall-score").textContent = result.overall;
    $("#score-ring").style.setProperty("--score", result.overall);
    const label = result.overall >= 80 ? "Excelente balance" : result.overall >= 65 ? "Buen estado visual" : result.overall >= 45 ? "Hay áreas por cuidar" : "Necesita atención";
    $("#score-label").textContent = label;
    $("#score-summary").textContent = summaryFor(result);
    $("#skin-type").textContent = result.skinType;
    $("#skin-type-copy").textContent = skinTypeCopy(result.skinType);
    $("#confidence-value").textContent = `${Math.round(result.confidence)}%`;
    $("#analysis-warnings").textContent = result.warnings?.length
      ? `Observaciones de captura: ${result.warnings.join(" ")}`
      : "";

    $("#metric-grid").innerHTML = result.metrics.map((item) => `
      <article class="metric-card">
        <div class="metric-card-top">
          <span class="metric-card-icon">${item.icon}</span>
          <b>${item.score}</b>
        </div>
        <h4>${item.name} · ${item.status}</h4>
        <p>${item.description}</p>
        <div class="mini-track"><span style="width:${item.score}%"></span></div>
      </article>
    `).join("");

    const priorities = result.metrics
      .filter((item) => !["Balance sebáceo"].includes(item.name))
      .sort((a, b) => a.score - b.score)
      .slice(0, 3);
    const baseRecommendations = priorities.map(recommendationFor);
    baseRecommendations.push({
      title: "Protección diaria",
      copy: "Finaliza cada mañana con protector solar de amplio espectro SPF 30 o superior y reaplica según exposición.",
    });
    $("#recommendations").innerHTML = baseRecommendations.slice(0, 4).map((item, index) => `
      <div class="recommendation">
        <span class="rec-number">0${index + 1}</span>
        <div><h4>${item.title}</h4><p>${item.copy}</p></div>
      </div>
    `).join("");

  }

  function summaryFor(result) {
    const weakest = [...result.metrics].sort((a, b) => a.score - b.score)[0];
    return `La principal oportunidad visible está en ${weakest.name.toLowerCase()}. Usa esta lectura como línea base y compara siempre con luz similar.`;
  }

  function skinTypeCopy(type) {
    const copies = {
      "Equilibrada": "El brillo y la apariencia de hidratación se perciben relativamente balanceados.",
      "Mixta": "Se observa mayor brillo en la zona T que en las mejillas.",
      "Mixta deshidratada": "La zona T presenta brillo mientras las mejillas muestran señales visuales de deshidratación.",
      "Grasa": "Se observa brillo más marcado y relativamente uniforme, especialmente en la zona T.",
      "Seca": "La microtextura y el bajo brillo sugieren priorizar confort e hidratación.",
    };
    return copies[type];
  }

  function recommendationFor(metricItem) {
    const recommendations = {
      "Hidratación": { title: "Refuerza la hidratación", copy: "Prueba una fórmula simple con glicerina, ácido hialurónico o ceramidas sobre piel ligeramente húmeda." },
      "Textura": { title: "Suaviza sin sobreexfoliar", copy: "Introduce exfoliación suave una o dos noches por semana y evita combinar varios activos irritantes." },
      "Poros": { title: "Cuida la zona T", copy: "Una limpieza amable y niacinamida pueden ayudar a mejorar visualmente el brillo y la apariencia de poros." },
      "Imperfecciones": { title: "Trata brotes con calma", copy: "Considera ácido salicílico a baja frecuencia. No manipules lesiones y consulta si son persistentes o dolorosas." },
      "Pigmentación": { title: "Uniforma y protege", copy: "La vitamina C o niacinamida pueden complementar el paso esencial: protector solar diario." },
      "Líneas visibles": { title: "Apoya la elasticidad", copy: "Prioriza hidratación y SPF. Si toleras retinoides, incorpóralos gradualmente con orientación profesional." },
      "Enrojecimiento": { title: "Calma la barrera", copy: "Simplifica la rutina y busca ingredientes calmantes como pantenol, centella o avena coloidal." },
    };
    return recommendations[metricItem.name] || { title: "Mantén una rutina simple", copy: "Limpieza suave, hidratación y protección solar forman una base sólida." };
  }

  function drawMap(result) {
    const canvas = $("#map-canvas");
    const image = $("#result-image");
    const render = () => {
      const rect = image.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * devicePixelRatio));
      canvas.height = Math.max(1, Math.round(rect.height * devicePixelRatio));
      const c = canvas.getContext("2d");
      c.scale(devicePixelRatio, devicePixelRatio);
      const w = rect.width, h = rect.height;
      const zones = Array.isArray(result.attentionZones) ? result.attentionZones : [];
      const naturalWidth = image.naturalWidth || captureCanvas.width;
      const naturalHeight = image.naturalHeight || captureCanvas.height;
      const coverScale = Math.max(w / naturalWidth, h / naturalHeight);
      const renderedWidth = naturalWidth * coverScale;
      const renderedHeight = naturalHeight * coverScale;
      const offsetX = (w - renderedWidth) / 2;
      const offsetY = (h - renderedHeight) / 2;

      zones.forEach((zone, index) => {
        const x = offsetX + zone.x * renderedWidth;
        const y = offsetY + zone.y * renderedHeight;
        const radius = Math.max(10, zone.radius * Math.max(renderedWidth, renderedHeight));
        const gradient = c.createRadialGradient(x, y, 2, x, y, radius * 1.7);
        gradient.addColorStop(0, `${zone.color}88`);
        gradient.addColorStop(.6, `${zone.color}36`);
        gradient.addColorStop(1, `${zone.color}00`);
        c.beginPath();
        c.arc(x, y, radius * 1.7, 0, Math.PI * 2);
        c.fillStyle = gradient;
        c.fill();
        c.beginPath();
        c.arc(x, y, radius, 0, Math.PI * 2);
        c.lineWidth = 2;
        c.strokeStyle = zone.color;
        c.stroke();
        c.beginPath();
        c.arc(x, y, 10, 0, Math.PI * 2);
        c.fillStyle = zone.color;
        c.fill();
        c.fillStyle = "#fff";
        c.font = "700 10px DM Sans";
        c.textAlign = "center";
        c.textBaseline = "middle";
        c.fillText(String(index + 1), x, y + .5);
      });

      const categories = [...new Map(zones.map((zone) => [zone.type, zone])).values()];
      $("#map-legend").innerHTML = categories.length
        ? categories.map((item) => `<span><i style="background:${item.color}"></i>${item.label}</span>`).join("")
        : `<span><i style="background:var(--lime-dark)"></i>Sin variaciones localizadas sobre el umbral</span>`;
      $("#map-findings").innerHTML = zones.length
        ? zones.map((zone, index) => `
          <div class="map-finding">
            <span class="map-finding-number" style="background:${zone.color}">${index + 1}</span>
            <div>
              <b>${zone.label} · ${zone.facialRegion}</b>
              <small>${zone.evidence}</small>
            </div>
            <small>${zone.level}</small>
          </div>
        `).join("")
        : `<p class="map-empty">El motor no encontró variaciones visuales localizadas con evidencia suficiente en esta captura. Esto no descarta afecciones de la piel.</p>`;
    };
    if (image.complete) setTimeout(render, 80);
    else image.onload = () => setTimeout(render, 80);
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
    })[character]);
  }

  function setReferralStatus(message, isError = false) {
    const status = $("#referral-status");
    status.textContent = message;
    status.style.color = isError ? "#ffb4a9" : "#cbd4cf";
  }

  async function searchClinics(latitude, longitude) {
    userLocation = { latitude, longitude };
    setReferralStatus("Buscando centros dentro de 50 km...");
    $("#clinic-grid").innerHTML = "";
    $("#lead-form").classList.remove("open");
    try {
      const params = new URLSearchParams({
        latitude: latitude.toString(),
        longitude: longitude.toString(),
        radius_km: "50",
        limit: "9",
      });
      const response = await fetch(`${API_BASE}/api/v1/clinics?${params}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudieron consultar los centros.");
      renderClinics(payload.items);
      setReferralStatus(payload.items.length
        ? `${payload.items.length} centros encontrados. Los perfiles “Demo” todavía no representan alianzas verificadas.`
        : "No encontramos centros registrados dentro del radio seleccionado.");
    } catch (error) {
      setReferralStatus(error.message || "No fue posible buscar centros.", true);
    }
  }

  async function searchStores(latitude, longitude) {
    userLocation = { latitude, longitude };
    setReferralStatus("Buscando tiendas dentro de 50 km...");
    $("#clinic-grid").innerHTML = "";
    $("#product-grid").innerHTML = "";
    try {
      const params = new URLSearchParams({
        latitude: latitude.toString(),
        longitude: longitude.toString(),
        radius_km: "50",
        limit: "9",
      });
      const response = await fetch(`${API_BASE}/api/v1/stores?${params}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudieron consultar las tiendas.");
      renderStores(payload.items);
      setReferralStatus(payload.items.length
        ? `${payload.items.length} tiendas encontradas. Los perfiles demo no representan convenios comerciales reales.`
        : "No encontramos tiendas registradas dentro del radio seleccionado.");
    } catch (error) {
      setReferralStatus(error.message || "No fue posible buscar tiendas.", true);
    }
  }

  function renderClinics(clinics) {
    $("#clinic-grid").innerHTML = clinics.map((clinic) => `
      <article class="clinic-card">
        <div class="clinic-badges">
          <span class="clinic-badge ${clinic.demo ? "demo" : ""}">${clinic.demo ? "Perfil demo" : clinic.verified ? "Verificado" : "En revisión"}</span>
          <span class="clinic-distance">${clinic.distanceKm} km</span>
        </div>
        <h4>${escapeHtml(clinic.name)}</h4>
        <p>${escapeHtml(clinic.address)} · ${escapeHtml(clinic.city)}</p>
        <div class="clinic-services">${clinic.services.map((service) => `<span>${escapeHtml(service)}</span>`).join("")}</div>
        <button class="button button-primary select-clinic" data-clinic='${escapeHtml(JSON.stringify(clinic))}'>Ver horarios</button>
      </article>
    `).join("");
  }

  function renderStores(stores) {
    $("#clinic-grid").innerHTML = stores.map((store) => `
      <article class="clinic-card store-card">
        <div class="clinic-badges">
          <span class="clinic-badge ${store.demo ? "demo" : ""}">${store.online ? "Tienda en línea" : store.demo ? "Tienda demo" : store.verified ? "Verificada" : "Referencia externa"}</span>
          <span class="clinic-distance">${store.online ? "Ecuador" : `${store.distanceKm} km`}</span>
        </div>
        <h4>${escapeHtml(store.name)}</h4>
        <p>${escapeHtml(store.address)} · ${escapeHtml(store.city)}</p>
        <button class="button button-primary select-store" data-store-id="${escapeHtml(store.id)}">Ver productos sugeridos</button>
      </article>
    `).join("");
  }

  $("#get-guidance").addEventListener("click", async () => {
    if (!lastReferralToken) {
      setReferralStatus(
        "La orientación, tiendas y citas requieren conectar el backend público.",
        true,
      );
      return;
    }
    const answers = {};
    $$("[data-guidance]").forEach((input) => {
      answers[input.dataset.guidance] = input.type === "checkbox"
        ? input.checked
        : input.value;
    });
    try {
      const response = await fetch(`${API_BASE}/api/v1/guidance`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Derma-Session": sessionId,
        },
        body: JSON.stringify({
          referralToken: lastReferralToken,
          answers,
          saveHistory: $("#save-guidance-history").checked,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudo generar la orientación.");
      const guidance = payload.guidance;
      guidanceRoute = guidance.route;
      $("#guidance-result").classList.add("visible");
      const components = guidance.components;
      $("#guidance-result").innerHTML = `
        <div class="guidance-score-head">
          <div><small>NIVEL ${escapeHtml(guidance.riskLevel)}</small><h4>${escapeHtml(guidance.title)}</h4></div>
          <b>${guidance.riskScore}<span>/100</span></b>
        </div>
        <p>${escapeHtml(guidance.message)}</p>
        <div class="risk-components">
          ${[
            ["Visión", components.vision],
            ["Síntomas", components.symptoms],
            ["Antecedentes", components.history],
          ].map(([label, component]) => `
            <div><span>${label} · ${component.weight}%</span><b>${component.contribution}</b><i><em style="width:${component.raw}%"></em></i></div>
          `).join("")}
        </div>
        <div class="guidance-reasons">${guidance.reasons.map((reason) => `<span>${escapeHtml(reason)}</span>`).join("")}</div>
        <small class="guidance-disclaimer">${escapeHtml(guidance.disclaimer)}${payload.stored ? " Guardada en tu historial." : ""}</small>`;
      $("#route-actions").classList.add("visible");
      $("#find-clinics").style.display = guidance.allowDermatologyBooking ? "inline-flex" : "none";
      $("#find-stores").style.display = guidance.allowProducts ? "inline-flex" : "none";
      $("#clinic-grid").innerHTML = "";
      $("#product-grid").innerHTML = "";
      setReferralStatus("");
    } catch (error) {
      setReferralStatus(error.message || "No se pudo generar la orientación.", true);
    }
  });

  $("#find-clinics").addEventListener("click", () => {
    if (!navigator.geolocation) {
      setReferralStatus("Este navegador no ofrece geolocalización. Puedes utilizar la ubicación demo.", true);
      return;
    }
    setReferralStatus("Esperando tu autorización de ubicación...");
    navigator.geolocation.getCurrentPosition(
      (position) => searchClinics(position.coords.latitude, position.coords.longitude),
      () => setReferralStatus("No se obtuvo la ubicación. Puedes usar la demo de Quito.", true),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  });

  $("#find-stores").addEventListener("click", () => {
    if (!navigator.geolocation) {
      setReferralStatus("Este navegador no ofrece geolocalización. Puedes utilizar la ubicación demo.", true);
      return;
    }
    setReferralStatus("Esperando tu autorización de ubicación...");
    navigator.geolocation.getCurrentPosition(
      (position) => searchStores(position.coords.latitude, position.coords.longitude),
      () => setReferralStatus("No se obtuvo la ubicación. Puedes usar la demo de Quito.", true),
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  });

  $("#use-demo-location").addEventListener("click", () => {
    if (guidanceRoute === "cosmetic-care") searchStores(-0.1807, -78.4678);
    else searchClinics(-0.1807, -78.4678);
  });

  $("#clinic-grid").addEventListener("click", async (event) => {
    const deleteButton = event.target.closest(".delete-lead");
    if (deleteButton) {
      deleteReferralLead(deleteButton.dataset.leadId);
      return;
    }
    const storeButton = event.target.closest(".select-store");
    if (storeButton) {
      await loadStoreProducts(storeButton.dataset.storeId);
      return;
    }
    const button = event.target.closest(".select-clinic");
    if (!button) return;
    selectedClinic = JSON.parse(button.dataset.clinic);
    $("#selected-clinic-name").textContent = selectedClinic.name;
    await loadAvailability(selectedClinic.id);
    $("#lead-form").classList.add("open");
    $("#submit-lead").innerHTML = `Solicitar cita <span>↗</span>`;
    $("#lead-form").scrollIntoView({ behavior: "smooth", block: "center" });
  });

  async function loadStoreProducts(storeId) {
    setReferralStatus("Preparando productos compatibles con tu evaluación...");
    try {
      const params = new URLSearchParams({ referral_token: lastReferralToken });
      const response = await fetch(`${API_BASE}/api/v1/stores/${encodeURIComponent(storeId)}/recommendations?${params}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudieron recomendar productos.");
      $("#product-grid").innerHTML = `
        <div class="routine-summary">
          <span>RUTINA PARA PIEL ${escapeHtml(payload.routine.skinType).toUpperCase()}</span>
          <h4>${payload.routine.steps.length} pasos esenciales</h4>
          <p>Mañana: limpieza → tratamiento opcional → hidratación → SPF. Noche: limpieza → tratamiento → hidratación.</p>
        </div>
      ` + payload.products.map((product) => `
        <article class="product-card">
          <small>${escapeHtml(product.routineStep || product.category)} · ${escapeHtml(product.brand || "")}</small>
          <h4>${escapeHtml(product.name)}</h4>
          <p>${escapeHtml(product.reason)}</p>
          <p><b>Ingredientes:</b> ${product.ingredients.map(escapeHtml).join(", ")}</p>
          <p><b>Uso:</b> ${escapeHtml(product.usage)}</p>
          <p class="product-skin-types"><b>Compatible con:</b> ${product.skinTypes.map(escapeHtml).join(", ")}</p>
          <div class="product-meta">
            <span>${escapeHtml(payload.store.name)} · verificado ${escapeHtml(product.verifiedAt || "sin fecha")}</span>
            <b>${product.price > 0 ? `$${product.price.toFixed(2)}` : "Ver precio"}</b>
          </div>
          <a class="button button-dark product-link" href="${escapeHtml(product.sourceUrl)}" target="_blank" rel="noopener noreferrer">Ver en tienda oficial ↗</a>
        </article>
      `).join("");
      setReferralStatus(payload.disclaimer);
      $("#product-grid").scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (error) {
      setReferralStatus(error.message || "No se pudieron cargar los productos.", true);
    }
  }

  async function loadAvailability(clinicId) {
    const field = $(".appointment-slot-field");
    const select = $("#appointment-slot");
    field.classList.add("visible");
    select.innerHTML = `<option value="">Cargando horarios...</option>`;
    try {
      const response = await fetch(`${API_BASE}/api/v1/clinics/${encodeURIComponent(clinicId)}/availability`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudo consultar disponibilidad.");
      select.innerHTML = `<option value="">Selecciona un horario</option>` + payload.items.map((slot) => {
        const label = new Intl.DateTimeFormat("es-EC", { dateStyle: "medium", timeStyle: "short" }).format(new Date(slot.startsAt));
        return `<option value="${escapeHtml(slot.id)}">${escapeHtml(label)}</option>`;
      }).join("");
      select.required = true;
    } catch (error) {
      select.innerHTML = `<option value="">Sin horarios disponibles</option>`;
      setReferralStatus(error.message || "No se pudo consultar disponibilidad.", true);
    }
  }

  $("#close-lead-form").addEventListener("click", () => {
    $("#lead-form").classList.remove("open");
    selectedClinic = null;
  });

  $("#lead-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!selectedClinic || !userLocation || !lastReferralToken) {
      setReferralStatus("Realiza un escaneo y selecciona un centro antes de enviar.", true);
      return;
    }
    const submit = $("#submit-lead");
    submit.disabled = true;
    submit.textContent = "Enviando...";
    const request = {
      clinicId: selectedClinic.id,
      referralToken: lastReferralToken,
      fullName: $("#lead-name").value.trim(),
      phone: $("#lead-phone").value.trim(),
      email: $("#lead-email").value.trim() || null,
      preferredChannel: $("#lead-channel").value,
      preferredTime: $("#lead-time").value.trim() || null,
      latitude: userLocation.latitude,
      longitude: userLocation.longitude,
      distanceKm: selectedClinic.distanceKm,
      consentContact: $("#consent-contact").checked,
      consentLocation: $("#consent-location").checked,
      consentResults: $("#consent-results").checked,
    };
    const appointmentSlot = $("#appointment-slot").value;
    if (appointmentSlot) request.slotId = appointmentSlot;
    try {
      const endpoint = appointmentSlot ? "/api/v1/appointments" : "/api/v1/leads";
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Derma-Session": sessionId,
        },
        body: JSON.stringify(request),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudo registrar la solicitud.");
      $("#lead-form").classList.remove("open");
      $("#clinic-grid").innerHTML = `
        <div class="lead-success">
          <b>${appointmentSlot ? "Solicitud de cita registrada" : "Solicitud registrada"}</b>
          <span>${escapeHtml(payload.message)} La fotografía no fue compartida. Código: ${escapeHtml(payload.leadId.slice(0, 8))}</span>
          <button class="button button-outline delete-lead" data-lead-id="${escapeHtml(payload.leadId)}">Eliminar solicitud</button>
        </div>`;
      setReferralStatus(`Solicitud enviada a ${payload.clinic.name}.`);
    } catch (error) {
      setReferralStatus(error.message || "No se pudo enviar la solicitud.", true);
    } finally {
      submit.disabled = false;
      submit.innerHTML = `Solicitar cita <span>↗</span>`;
    }
  });

  async function deleteReferralLead(leadId) {
    try {
      const response = await fetch(`${API_BASE}/api/v1/leads/${encodeURIComponent(leadId)}`, {
        method: "DELETE",
        headers: { "X-Derma-Session": sessionId },
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.error?.message || "No se pudo eliminar.");
      $("#clinic-grid").innerHTML = "";
      setReferralStatus("La solicitud y sus datos fueron eliminados.");
    } catch (error) {
      setReferralStatus(error.message || "No se pudo eliminar la solicitud.", true);
    }
  }

  $("#restart-scan").addEventListener("click", () => {
    imageReady = false;
    sourceMode = null;
    lastReferralToken = null;
    userLocation = null;
    selectedClinic = null;
    guidanceRoute = null;
    upload.value = "";
    preview.removeAttribute("src");
    preview.style.display = "none";
    video.style.display = "none";
    cameraPlaceholder.style.display = "flex";
    cameraPlaceholder.querySelector("b").textContent = "Activa la cámara o sube una foto";
    cameraPlaceholder.querySelector("span").textContent = "La imagen se procesa solo en este dispositivo.";
    cameraStatus.textContent = "Esperando imagen";
    analyzeButton.disabled = true;
    $$(".quality-item").forEach((row) => {
      row.classList.remove("good", "warn");
      $("i", row).textContent = "—";
    });
    $("#progress-bar").style.width = "0";
    $("#progress-value").textContent = "0%";
    $("#clinic-grid").innerHTML = "";
    $("#referral-status").textContent = "";
    $("#lead-form").classList.remove("open");
    $("#lead-form").reset();
    $("#product-grid").innerHTML = "";
    $("#guidance-result").classList.remove("visible");
    $("#guidance-result").innerHTML = "";
    $("#route-actions").classList.remove("visible");
    $$("[data-guidance]").forEach((input) => {
      if (input.type === "checkbox") input.checked = false;
      else input.selectedIndex = 0;
    });
    $("#save-guidance-history").checked = false;
    showStage("capture");
  });
})();
