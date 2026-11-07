import { ref, onUnmounted } from "vue";
import { api } from "./api";
import { ClassroomAudio } from "./classroomAudio";
import { classroomCapabilitiesError } from "./classroomStatus.js";
import { emptyReply, reduceReply } from "./classroomInteraction.js";
import { CAMERA_HEIGHTS, cameraConstraints, inferenceSize } from './classroomMedia.js';

export function useClassroom() {
  const room = ref(null),
    capabilities = ref(null),
    events = ref([]),
    error = ref(""),
    state = ref("idle");
  const capabilitiesLoading = ref(false), capabilitiesError = ref('');
  const partial = ref(""),
    students = ref([]),
    activeStudent = ref(null),
    raised = ref(null),
    mouth = ref(0);
  const reply = ref(emptyReply()),
    playbackStudent = ref(null);
  const volume = ref(1), cameraResolution = ref(720), cameraAdjusting = ref(false), cameraNote = ref('');
  const landmarks = ref(null),
    motionStatus = ref("idle"),
    handStatus = ref("idle"),
    faceStatus = ref("idle"),
    cameraEnabled = ref(false);
  const pose = ref(null),
    camera = ref(null),
    elapsed = ref(0),
    cloudVision = ref(false),
    busy = ref(false);
  const wallElapsed = ref(0), audioForRecording = ref(null);
  let wallBase = 0;
  let evidenceStartedAt = Infinity;
  let ws,
    audio,
    cameraStream,
    poseWorker,
    poseReady = false,
    frameBusy = false,
    visionBusy = false;
  let clock,
    frameTimer,
    visionTimer,
    pollTimer,
    baseTime,
    connectTimeout,
    disposed = false,
    polling = false;
  const seen = new Set();
  let motionTimeout,
    lastMotionSent = -Infinity,
    cameraPending = false;
  const send = (type, payload = {}) => {
    if (ws?.readyState === WebSocket.OPEN && ws.bufferedAmount < 200000) {
      ws.send(
        JSON.stringify({ type, event_id: crypto.randomUUID(), ...payload }),
      );
    } else if (
      ws?.readyState === WebSocket.OPEN &&
      ws.bufferedAmount >= 200000
    ) {
      error.value = "网络不畅，部分音频未送达，请重新连接。";
      ws.close();
    }
  };
  async function refreshCapabilities() {
    if (capabilitiesLoading.value || disposed) return;
    capabilitiesLoading.value = true;
    capabilitiesError.value = '';
    try {
      const { data } = await api.get("/classroom/capabilities", { timeout: 10000, skipBusy: true });
      if (!disposed) capabilities.value = data;
    } catch (e) {
      if (!disposed) capabilitiesError.value = classroomCapabilitiesError(e);
    } finally {
      capabilitiesLoading.value = false;
    }
  }
  async function load(sid) {
    if (room.value?.session_id !== Number(sid)) reply.value = emptyReply();
    room.value = (await api.get(`/classroom/sessions/${sid}`)).data;
    events.value = room.value.events || [];
    seen.clear();
    events.value.forEach((e) => seen.add(e.id));
    wallElapsed.value = room.value.wall_elapsed ?? room.value.elapsed;
    wallBase = performance.now() - wallElapsed.value * 1000;
    elapsed.value = room.value.active_elapsed ?? room.value.elapsed;
    syncClock(room.value.elapsed, room.value.state === 'active');
    cloudVision.value = room.value.cloud_vision;
    if (room.value.state === "ended") state.value = "ended";
    else if (room.value.state === 'paused') state.value = 'paused';
  }
  function syncClock(seconds, running = true) {
    clearInterval(clock);
    elapsed.value = Math.max(0, Number(seconds) || 0);
    baseTime = performance.now() - elapsed.value * 1000;
    if (running) clock = setInterval(() => {
      elapsed.value = Math.max(0, (performance.now() - baseTime) / 1000);
      wallElapsed.value = Math.max(0, (performance.now() - wallBase) / 1000);
    }, 250);
  }
  async function connect() {
    if (disposed) return;
    state.value = "connecting";
    error.value = "";
    const { data } = await api.post(
      `/classroom/sessions/${room.value.session_id}/ticket`,
    );
    ws = new WebSocket(
      `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/api/classroom/live`,
    );
    const socket = ws;
    let lastSequence = 0;
    socket.onopen = () => socket.send(JSON.stringify({ ticket: data.ticket }));
    connectTimeout = setTimeout(() => {
      if (state.value === "connecting") {
        error.value = "语音连接超时，请检查服务配置后重连";
        socket.close();
      }
    }, 20000);
    socket.onmessage = async ({ data }) => {
      if (disposed || socket !== ws) return;
      const m = JSON.parse(data);
      if (
        m.session_id !== room.value?.session_id ||
        !Number.isInteger(m.seq) ||
        m.seq <= lastSequence
      )
        return;
      lastSequence = m.seq;
      if (
        ["finishing", "ended"].includes(state.value) &&
        (m.type.startsWith("generation_") ||
          ["reply_delta", "reply", "raise", "audio", "audio_end"].includes(
            m.type,
          ))
      )
        return;
      reply.value = reduceReply(reply.value, m);
      if (m.type === "connected") {
        wallElapsed.value = m.wall_elapsed ?? m.elapsed;
        wallBase = performance.now() - wallElapsed.value * 1000;
        students.value = m.students;
        syncClock(m.elapsed);
      }
      if (m.type === "budget" && capabilities.value)
        capabilities.value.budget = m.budget;
      if (m.type === "ready") {
        clearTimeout(connectTimeout);
        evidenceStartedAt = performance.now();
        state.value = "listening";
      }
      if (m.type === "event" && !seen.has(m.event.id)) {
        seen.add(m.event.id);
        events.value.push(m.event);
        if (['student', 'learning', 'playback'].includes(m.event.type) && m.event.data.states)
          room.value.students = m.event.data.states;
      }
      if (m.type === "partial") partial.value = m.text;
      if (m.type === "speech_stopped" && audio)
        audio.lastSpeech = performance.now();
      if (m.type === "reply") {
        activeStudent.value = m.student_id;
        raised.value = null;
        state.value = "speaking";
      }
      if (m.type === "raise") raised.value = m.student_id;
      if (m.type === "audio") audio?.chunk(m.reply_id, m.audio, m.sample_rate);
      if (m.type === "audio_end") {
        audio?.end(m.reply_id, m.ok);
        if (m.ok === false) error.value = "学生语音播放失败，可查看回复文字。";
      }
      if (m.type === "cancel") {
        if (m.states) room.value.students = m.states;
        playbackStudent.value = null;
        audio?.cancel(m.reply_id);
        activeStudent.value = null;
        if (state.value !== "finishing") state.value = "listening";
      }
      if (m.type === "listening") {
        playbackStudent.value = null;
        activeStudent.value = null;
        if (state.value !== "finishing") state.value = "listening";
      }
      if (m.type === "error") error.value = m.message;
      if (m.type === "ended") {
        playbackStudent.value = null;
        state.value = "ended";
        clearInterval(clock);
        await audio?.close();
        stopCamera();
        socket.close();
        startPolling();
      }
    };
    socket.onclose = () => {
      if (socket !== ws) return;
      reply.value = emptyReply();
      playbackStudent.value = null;
      activeStudent.value = null;
      raised.value = null;
      clearTimeout(connectTimeout);
      audio?.close();
      stopCamera();
      if (state.value !== "ended" && !disposed) {
        clearInterval(clock);
        state.value = "disconnected";
        error.value ||= "连接已断开，已保存记录保留。请点击重连。";
      }
    };
    socket.onerror = () => {
      error.value = "课堂连接失败，请检查网络后重连。";
    };
  }
  function consentReady(consent, cameraConsent) {
    if (consent === true && cameraConsent === true) return true;
    error.value = '请先同意语音识别与 AI 评课，以及开启摄像头。';
    return false;
  }
  async function prepareDevices() {
    await prepareAudio();
    if (disposed) return;
    if (!cameraEnabled.value) await toggleCamera();
    if (!cameraEnabled.value) throw new Error(error.value || '摄像头不可用，无法开始课堂');
  }
  async function begin(mode, consent, cameraConsent, practicePlanId = null) {
    if (busy.value) return;
    if (!consentReady(consent, cameraConsent)) return;
    busy.value = true;
    error.value = "";
    try {
      state.value = "connecting";
      await prepareDevices();
      if (disposed) return;
      const { data } = await api.post("/classroom/sessions", {
        mode,
        audio_consent: consent,
        camera_consent: cameraConsent,
        cloud_vision: cloudVision.value,
        ...(practicePlanId ? { practice_plan_id: practicePlanId } : {}),
      });
      await load(data.session_id);
      await connect();
    } catch (e) {
      await audio?.close();
      stopCamera();
      error.value = e.response?.data?.message || e.message || "课堂启动失败";
      state.value = room.value ? "disconnected" : "idle";
    } finally {
      busy.value = false;
    }
  }
  async function reconnect(consent, cameraConsent) {
    if (busy.value) return;
    if (!consentReady(consent, cameraConsent) || !room.value) return;
    busy.value = true;
    try {
      // A browser close event is asynchronous; invalidate it before opening new devices.
      const previousSocket = ws;
      ws = null;
      previousSocket?.close();
      state.value = 'connecting';
      await prepareDevices();
      await load(room.value.session_id);
      if (room.value.state === 'paused') {
        const { data } = await api.post(`/classroom/sessions/${room.value.session_id}/resume`, {}, {timeout:10000,skipBusy:true});
        room.value = {...room.value, ...data};
      }
      if (room.value.state === "active") await connect();
      else { await audio?.close(); stopCamera(); }
    } catch (e) {
      await audio?.close();
      stopCamera();
      await audio?.close();
      stopCamera();
      error.value = e.message || "重连失败，请稍后重试";
      state.value = room.value?.state === 'ended' ? 'ended' : 'disconnected';
    } finally {
      busy.value = false;
    }
  }
  async function finish() {
    if (!room.value || busy.value) return;
    if (elapsed.value < 10) {
      error.value = '授课至少满 10 秒后才能结束并评课。';
      return;
    }
    busy.value = true;
    state.value = "finishing";
    reply.value = emptyReply();
    playbackStudent.value = null;
    audio?.cancel();
    await audio?.stopCapture(true);
    send("finish");
    try {
      await api.post(`/classroom/sessions/${room.value.session_id}/finish`);
      startPolling();
    } catch (e) {
      error.value = e.response?.data?.message || "结束请求失败，记录已保留，请重试";
      state.value = "disconnected";
    } finally {
      busy.value = false;
    }
  }
  function startPolling() {
    clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      if (polling || disposed) return;
      polling = true;
      try {
        await load(room.value.session_id);
        if (room.value.state === "ended") {
          clearInterval(clock);
          await audio?.close();
          stopCamera();
          ws?.close();
        }
        if (["completed", "failed", "insufficient"].includes(room.value.report_state))
          clearInterval(pollTimer);
      } catch {
        error.value = "报告状态读取失败，可稍后从历史课堂继续查看";
      } finally {
        polling = false;
      }
    }, 2000);
  }
  async function prepareAudio() {
    // Called from a user gesture, so AudioContext can resume before the WebSocket handshake.
    await audio?.close();
    audio = new ClassroomAudio(
      send,
      (value) => {
        mouth.value = value;
      },
      (id, phase) => {
        if (reply.value.replyId !== id) return;
        playbackStudent.value =
          phase === "playing" ? reply.value.studentId : null;
        reply.value = {
          ...reply.value,
          phase,
          error: phase === "failed" ? "语音播放失败，可查看回复文字" : "",
        };
      },
    );
    audio.setVolume(volume.value);
    try {
      await audio.start();
      audioForRecording.value = () => audio?.recordingStream();
    } catch {
      throw new Error("麦克风不可用，请允许权限并检查设备");
    }
  }
  function setVolume(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return;
    volume.value = Math.max(0, Math.min(1, number));
    audio?.setVolume(volume.value);
  }
  function describeCamera() {
    const settings = cameraStream?.getVideoTracks?.()[0]?.getSettings?.();
    cameraNote.value = settings?.width && settings?.height ? `实际画面 ${settings.width}×${settings.height}` : '';
  }
  async function setCameraResolution(value) {
    const height = Number(value);
    if (!CAMERA_HEIGHTS.includes(height) || cameraAdjusting.value) return;
    const stream = cameraStream;
    if (!stream) { cameraResolution.value = height; return; }
    cameraAdjusting.value = true;
    try {
      await stream.getVideoTracks()[0].applyConstraints(cameraConstraints(height));
      if (stream !== cameraStream) return;
      cameraResolution.value = height;
      describeCamera();
    } catch {
      if (stream === cameraStream) cameraNote.value = '设备不支持此设置，分辨率未切换；当前镜头仍可使用。';
    } finally { cameraAdjusting.value = false; }
  }
  async function regenerate(objection = "") {
    error.value = "";
    busy.value = true;
    try {
      await api.post(`/classroom/sessions/${room.value.session_id}/report`, {
        objection,
      });
      await load(room.value.session_id);
      startPolling();
    } catch (e) {
      error.value = e.response?.data?.message || "报告重试失败";
    } finally {
      busy.value = false;
    }
  }
  function initializeMotion() {
    clearTimeout(motionTimeout);
    poseWorker?.terminate();
    poseReady = frameBusy = false;
    motionStatus.value = handStatus.value = faceStatus.value = "loading";
    lastMotionSent = -Infinity;
    poseWorker = new Worker(new URL("./pose.worker.js", import.meta.url), {
      type: "module",
    });
    const worker = poseWorker;
    motionTimeout = setTimeout(() => {
      if (worker !== poseWorker) return;
      worker.terminate();
      poseReady = frameBusy = false;
      motionStatus.value = "failed";
      handStatus.value = faceStatus.value = "failed";
      landmarks.value = null;
    }, 20000);
    poseWorker.onmessage = ({ data }) => {
      if (worker !== poseWorker) return;
      if (["ready", "pose", "error"].includes(data.type)) frameBusy = false;
      if (data.type === "ready") {
        clearTimeout(motionTimeout);
        poseReady = true;
        motionStatus.value = "ready";
      }
      if (data.type === "hands_status") handStatus.value = data.status;
      if (data.type === "face_status") faceStatus.value = data.status;
      if (data.type === "pose") {
        pose.value = data.data;
        landmarks.value = {
          body: data.landmarks || [],
          hands: data.hands || [],
          face: data.face || [],
          at: data.captured_at ?? performance.now(),
        };
        const now = performance.now();
        if (Number.isFinite(data.captured_at) && data.captured_at >= evidenceStartedAt &&
            now - landmarks.value.at < 1500 && now - lastMotionSent >= 2100) {
          send("pose", { data: data.data });
          lastMotionSent = now;
        }
      }
      if (data.type === "error") {
        clearTimeout(motionTimeout);
        error.value = data.message;
        poseReady = false;
        motionStatus.value = "failed";
        handStatus.value = faceStatus.value = "failed";
        pose.value = null;
        landmarks.value = null;
      }
    };
    poseWorker.onerror = () => {
      if (worker !== poseWorker) return;
      clearTimeout(motionTimeout);
      frameBusy = false;
      error.value = "动作检测暂不可用，镜头仍可使用。";
      motionStatus.value = "failed";
      handStatus.value = faceStatus.value = "failed";
      pose.value = null;
      poseReady = false;
      landmarks.value = null;
    };
    poseWorker.postMessage({ type: "init" });
  }
  function stopCamera() {
    evidenceStartedAt = Infinity;
    clearTimeout(motionTimeout);
    clearInterval(frameTimer);
    clearInterval(visionTimer);
    cameraStream?.getTracks().forEach((t) => { t.onended = null; t.stop(); });
    cameraStream = null;
    cameraEnabled.value = false;
    cameraNote.value = '';
    landmarks.value = null;
    motionStatus.value = handStatus.value = faceStatus.value = "idle";
    if (camera.value) camera.value.srcObject = null;
    poseWorker?.terminate();
    poseWorker = null;
    poseReady = false;
    frameBusy = false;
    pose.value = null;
  }
  async function previewCamera(cameraConsent) {
    if (busy.value || disposed || !['idle', 'disconnected'].includes(state.value)) return;
    if (cameraConsent !== true) {
      error.value = '请先勾选「同意摄像头开启」，再打开摄像头预览。';
      return;
    }
    if (cameraEnabled.value) return;
    // Share the device lock with begin/reconnect; preview never prepares audio or creates a session.
    busy.value = true;
    try {
      await toggleCamera();
    } finally {
      busy.value = false;
    }
  }
  async function toggleCamera() {
    if (cameraPending) return;
    if (cameraStream) {
      pauseCapture();
      return;
    }
    try {
      error.value = "正在等待摄像头授权；若浏览器未弹窗，请在地址栏检查权限。";
      cameraPending = true;
      let timedOut = false,
        timer;
      const request = navigator.mediaDevices
        .getUserMedia({ video: cameraConstraints(cameraResolution.value), audio: false })
        .then((stream) => {
          if (timedOut || disposed) {
            stream.getTracks().forEach((t) => t.stop());
            throw new Error("Camera request expired");
          }
          return stream;
        });
      try {
        cameraStream = await Promise.race([
          request,
          new Promise((_, reject) => {
            timer = setTimeout(() => {
              timedOut = true;
              reject(new Error("Camera permission timeout"));
            }, 15000);
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
      error.value = "";
      camera.value.srcObject = cameraStream;
      await camera.value.play();
      cameraEnabled.value = true;
      cameraStream.getVideoTracks().forEach(track => {
        track.onended = () => pauseCapture('摄像头已断开，采集已停止。检查设备后可重新连接。');
      });
      describeCamera();
      initializeMotion();
      frameTimer = setInterval(async () => {
        if (!poseReady || frameBusy || !camera.value?.videoWidth) return;
        frameBusy = true;
        const worker = poseWorker;
        try {
          const image = await createImageBitmap(camera.value, inferenceSize(camera.value.videoWidth, camera.value.videoHeight || 480));
          if (!worker || worker !== poseWorker) {
            image.close();
            return;
          }
          worker.postMessage({ image, time: performance.now() }, [image]);
        } catch {
          frameBusy = false;
        }
      }, 100);
      visionTimer = setInterval(() => {
        if (
          !cloudVision.value ||
          visionBusy ||
          !camera.value?.videoWidth ||
          !["listening", "speaking"].includes(state.value)
        )
          return;
        visionBusy = true;
        const canvas = document.createElement("canvas");
        canvas.width = 640;
        canvas.height = 480;
        canvas.getContext("2d").drawImage(camera.value, 0, 0, 640, 480);
        send("image", { image: canvas.toDataURL("image/jpeg", 0.65) });
        visionBusy = false;
      }, 15000);
    } catch {
      stopCamera();
      error.value = "摄像头不可用，请允许权限并检查设备；镜头开启后才能授课。";
    } finally {
      cameraPending = false;
    }
  }
  async function pauseCapture(message = '课堂已暂停，设备与倒计时均已停止。') {
    if (message !== '课堂已暂停，设备与倒计时均已停止。') error.value = message;
    clearInterval(clock);
    const previous = ws;
    ws = null; // Invalidate close callbacks before asynchronous pause acknowledgement.
    stopCamera();
    audio?.close();
    if (room.value && room.value.state !== 'ended') {
      busy.value = true;
      state.value = 'paused';
      try {
        const {data} = await api.post(`/classroom/sessions/${room.value.session_id}/pause`, {}, {timeout:10000,skipBusy:true});
        room.value = {...room.value, ...data};
        elapsed.value = data.active_elapsed ?? data.elapsed ?? elapsed.value;
      } catch {
        error.value = '设备已停止，暂停状态尚未确认；恢复前将重新读取服务端状态。';
      } finally {
        busy.value = false;
      }
    }
    previous?.close();
  }
  function setVision() {
    send("vision_consent", { enabled: cloudVision.value });
  }
  function retryMotion() {
    if (!poseWorker) return;
    if (motionStatus.value === "failed") {
      initializeMotion();
    } else {
      handStatus.value = faceStatus.value = "loading";
      poseWorker.postMessage({ type: "retry_hands" });
    }
  }
  onUnmounted(() => {
    disposed = true;
    clearTimeout(connectTimeout);
    clearInterval(clock);
    clearInterval(pollTimer);
    stopCamera();
    audio?.close();
    ws?.close();
  });
  return {
    room,
    wallElapsed,
    audioForRecording,
    volume,
    setVolume,
    cameraResolution,
    cameraAdjusting,
    cameraNote,
    setCameraResolution,
    reply,
    playbackStudent,
    landmarks,
    motionStatus,
    handStatus,
    faceStatus,
    cameraEnabled,
    retryMotion,
    capabilities,
    capabilitiesLoading,
    capabilitiesError,
    events,
    error,
    state,
    partial,
    students,
    activeStudent,
    raised,
    mouth,
    pose,
    camera,
    elapsed,
    cloudVision,
    busy,
    send,
    refreshCapabilities,
    begin,
    reconnect,
    finish,
    load,
    regenerate,
    previewCamera,
    toggleCamera,
    pauseCapture,
    setVision,
  };
}
