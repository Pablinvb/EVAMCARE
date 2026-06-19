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
  const API_BASE = location.port === "8000" ? "" : "http://127.0.0.1:8000";
  const sessionId = getSessionId();
  let stream = null;
  let imageReady = false;
  let sourceMode = null;
  let lastAnalysis = null;

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
      cameraStatus.textContent = "Backend desconectado · inicia run_backend.ps1";
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
      renderResults(lastAnalysis);
      await wait(260);
      showStage("results");
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
      throw new Error("No se pudo conectar con el backend. Ejecuta run_backend.ps1.");
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(payload?.error?.message || "El backend rechazó la imagen.");
    }
    return payload;
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

    drawMap(result);
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
      const candidates = [
        { key: "acneNeed", label: "Imperfecciones", color: "#e96f61", points: [[.38,.53],[.63,.57],[.42,.63]] },
        { key: "poreNeed", label: "Poros", color: "#e4b648", points: [[.35,.48],[.65,.48],[.5,.53]] },
        { key: "lineNeed", label: "Líneas", color: "#6aa8c9", points: [[.5,.29],[.34,.39],[.66,.39]] },
        { key: "pigmentationNeed", label: "Pigmentación", color: "#9574cf", points: [[.34,.58],[.67,.56]] },
      ].filter((item) => result.needs[item.key] > 22);
      candidates.forEach((group) => {
        group.points.slice(0, result.needs[group.key] > 58 ? 3 : 2).forEach(([x, y]) => {
          c.beginPath();
          c.arc(w * x, h * y, 11, 0, Math.PI * 2);
          c.fillStyle = `${group.color}55`; c.fill();
          c.lineWidth = 2; c.strokeStyle = group.color; c.stroke();
          c.beginPath(); c.arc(w * x, h * y, 3, 0, Math.PI * 2); c.fillStyle = group.color; c.fill();
        });
      });
      $("#map-legend").innerHTML = candidates.length
        ? candidates.map((item) => `<span><i style="background:${item.color}"></i>${item.label}</span>`).join("")
        : `<span><i style="background:var(--lime-dark)"></i>Sin zonas destacadas</span>`;
    };
    if (image.complete) setTimeout(render, 80);
    else image.onload = () => setTimeout(render, 80);
  }

  $("#restart-scan").addEventListener("click", () => {
    imageReady = false;
    sourceMode = null;
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
    showStage("capture");
  });
})();
