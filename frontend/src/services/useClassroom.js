import { ref, onUnmounted } from "vue";
import { api } from "./api";
import { ClassroomAudio } from "./classroomAudio";
import { classroomLoadError } from "./classroomStatus.js";
import { emptyReply, reduceReply } from "./classroomInteraction.js";

export function useClassroom() {
  const room = ref(null),
    capabilities = ref(null),
    events = ref([]),
    error = ref(""),
    state = ref("idle");
  const partial = ref(""),
    students = ref([]),
    activeStudent = ref(null),
    raised = ref(null),
    mouth = ref(0);
  const reply = ref(emptyReply()),
    playbackStudent = ref(null);
  const landmarks = ref(null),
    motionStatus = ref("idle"),
    handStatus = ref("idle"),
    cameraEnabled = ref(false);
  const pose = ref(null),
    camera = ref(null),
    elapsed = ref(0),
    cloudVision = ref(false),
    busy = ref(false);
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
    try {
      capabilities.value = (await api.get("/classroom/capabilities")).data;
    } catch (e) {
      error.value = classroomLoadError(e, "无法读取课堂状态，请稍后刷新。");
    }
  }
  async function load(sid) {
    if (room.value?.session_id !== Number(sid)) reply.value = emptyReply();
    room.value = (await api.get(`/classroom/sessions/${sid}`)).data;
    events.value = room.value.events || [];
    seen.clear();
    events.value.forEach((e) => seen.add(e.id));
    elapsed.value = room.value.elapsed;
    cloudVision.value = room.value.cloud_vision;
    if (room.value.state === "ended") state.value = "ended";
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
        students.value = m.students;
        baseTime = performance.now() - m.elapsed * 1000;
        clearInterval(clock);
        clock = setInterval(() => {
          elapsed.value = (performance.now() - baseTime) / 1000;
        }, 250);
      }
      if (m.type === "budget" && capabilities.value)
        capabilities.value.budget = m.budget;
      if (m.type === "ready") {
        clearTimeout(connectTimeout);
        state.value = "listening";
      }
      if (m.type === "event" && !seen.has(m.event.id)) {
        seen.add(m.event.id);
        events.value.push(m.event);
        if (m.event.type === "student")
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
      clearInterval(clock);
      if (state.value !== "ended" && !disposed) {
        state.value = "disconnected";
        error.value ||= "连接已断开，已保存记录保留。请点击重连。";
      }
    };
    socket.onerror = () => {
      error.value = "课堂连接失败，请检查网络后重连。";
    };
  }
  async function begin(mode, consent) {
    if (busy.value) return;
    busy.value = true;
    error.value = "";
    try {
      state.value = "connecting";
      await prepareAudio();
      if (disposed) return;
      const { data } = await api.post("/classroom/sessions", {
        mode,
        audio_consent: consent,
        cloud_vision: cloudVision.value,
      });
      await load(data.session_id);
      await connect();
    } catch (e) {
      await audio?.close();
      error.value = e.response?.data?.message || e.message || "课堂启动失败";
      state.value = room.value ? "disconnected" : "idle";
    } finally {
      busy.value = false;
    }
  }
  async function reconnect() {
    if (busy.value) return;
    busy.value = true;
    try {
      await prepareAudio();
      await load(room.value.session_id);
      if (room.value.state === "active") await connect();
      else await audio?.close();
    } catch (e) {
      await audio?.close();
      error.value = e.message || "重连失败，请稍后重试";
    } finally {
      busy.value = false;
    }
  }
  async function finish() {
    if (!room.value || busy.value) return;
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
    } catch {
      error.value = "结束请求失败，记录已保留，请重试";
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
        if (["completed", "failed"].includes(room.value.report_state))
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
    try {
      await audio.start();
    } catch {
      throw new Error("麦克风不可用，请允许权限并检查设备");
    }
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
    motionStatus.value = handStatus.value = "loading";
    poseWorker = new Worker(new URL("./pose.worker.js", import.meta.url), {
      type: "module",
    });
    const worker = poseWorker;
    motionTimeout = setTimeout(() => {
      if (worker !== poseWorker) return;
      worker.terminate();
      poseReady = frameBusy = false;
      motionStatus.value = "failed";
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
      if (data.type === "pose") {
        pose.value = data.data;
        landmarks.value = {
          body: data.landmarks || [],
          hands: data.hands || [],
          at: performance.now(),
        };
        send("pose", { data: data.data });
      }
      if (data.type === "error") {
        clearTimeout(motionTimeout);
        error.value = data.message;
        poseReady = false;
        motionStatus.value = "failed";
        landmarks.value = null;
      }
    };
    poseWorker.onerror = () => {
      if (worker !== poseWorker) return;
      clearTimeout(motionTimeout);
      frameBusy = false;
      error.value = "动作检测暂不可用，镜头仍可使用。";
      motionStatus.value = "failed";
      poseReady = false;
      landmarks.value = null;
    };
    poseWorker.postMessage({ type: "init" });
  }
  function stopCamera() {
    clearTimeout(motionTimeout);
    clearInterval(frameTimer);
    clearInterval(visionTimer);
    cameraStream?.getTracks().forEach((t) => t.stop());
    cameraStream = null;
    cameraEnabled.value = false;
    landmarks.value = null;
    motionStatus.value = handStatus.value = "idle";
    if (camera.value) camera.value.srcObject = null;
    poseWorker?.terminate();
    poseWorker = null;
    poseReady = false;
    frameBusy = false;
    pose.value = null;
  }
  async function toggleCamera() {
    if (cameraPending) return;
    if (cameraStream) {
      stopCamera();
      return;
    }
    try {
      error.value = "正在等待摄像头授权；若浏览器未弹窗，请在地址栏检查权限。";
      cameraPending = true;
      let timedOut = false,
        timer;
      const request = navigator.mediaDevices
        .getUserMedia({ video: { width: 640, height: 480 }, audio: false })
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
      initializeMotion();
      frameTimer = setInterval(async () => {
        if (!poseReady || frameBusy || !camera.value?.videoWidth) return;
        frameBusy = true;
        const worker = poseWorker;
        try {
          const image = await createImageBitmap(camera.value);
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
      error.value = "摄像头不可用，请检查权限；仍可进行语音课堂";
    } finally {
      cameraPending = false;
    }
  }
  function setVision() {
    send("vision_consent", { enabled: cloudVision.value });
  }
  function retryMotion() {
    if (!poseWorker) return;
    if (motionStatus.value === "failed") {
      initializeMotion();
    } else {
      handStatus.value = "loading";
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
    reply,
    playbackStudent,
    landmarks,
    motionStatus,
    handStatus,
    cameraEnabled,
    retryMotion,
    capabilities,
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
    toggleCamera,
    setVision,
  };
}
