import { ref, onUnmounted } from "vue";
import { api } from "./api";
import { ClassroomAudio } from "./classroomAudio";

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
  const send = (type, payload = {}) => {
    if (ws?.readyState === WebSocket.OPEN && ws.bufferedAmount < 200000) {
      ws.send(
        JSON.stringify({ type, event_id: crypto.randomUUID(), ...payload }),
      );
    } else if (
      ws?.readyState === WebSocket.OPEN &&
      ws.bufferedAmount >= 200000
    ) {
      error.value = "网络发送积压，部分音频未送达，请重连；缺失内容不会补造";
      ws.close();
    }
  };
  async function refreshCapabilities() {
    try {
      capabilities.value = (await api.get("/classroom/capabilities")).data;
    } catch {
      error.value = "无法读取服务状态，请确认后端已启动";
    }
  }
  async function load(sid) {
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
      if (m.session_id !== room.value?.session_id || !Number.isInteger(m.seq) || m.seq <= lastSequence) return;
      lastSequence = m.seq;
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
        if (m.event.type === "student") room.value.students = m.event.data.states;
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
        if (m.ok === false) error.value = "文字已生成，语音播放失败；未记为完整发言。";
      }
      if (m.type === "cancel") {
        audio?.cancel(m.reply_id);
        activeStudent.value = null;
        if (state.value !== "finishing") state.value = "listening";
      }
      if (m.type === "listening") {
        activeStudent.value = null;
        if (state.value !== "finishing") state.value = "listening";
      }
      if (m.type === "error") error.value = m.message;
      if (m.type === "ended") {
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
      clearTimeout(connectTimeout);
      audio?.close();
      clearInterval(clock);
      if (state.value !== "ended" && !disposed) {
        state.value = "disconnected";
        error.value ||= "连接已断开，已保存记录保留。请点击重连。";
      }
    };
    socket.onerror = () => {
      error.value = "实时连接失败，请检查后端和网络";
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
    audio = new ClassroomAudio(send, (value) => {
      mouth.value = value;
    });
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
  function stopCamera() {
    clearInterval(frameTimer);
    clearInterval(visionTimer);
    cameraStream?.getTracks().forEach((t) => t.stop());
    cameraStream = null;
    if (camera.value) camera.value.srcObject = null;
    poseWorker?.terminate();
    poseWorker = null;
    poseReady = false;
    frameBusy = false;
    pose.value = null;
  }
  async function toggleCamera() {
    if (cameraStream) {
      stopCamera();
      return;
    }
    try {
      error.value = "正在等待摄像头授权；若浏览器未弹窗，请在地址栏检查权限。";
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
      poseWorker = new Worker(new URL("./pose.worker.js", import.meta.url), {
        type: "module",
      });
      poseWorker.onmessage = ({ data }) => {
        frameBusy = false;
        if (data.type === "ready") poseReady = true;
        if (data.type === "pose") {
          pose.value = data.data;
          send("pose", { data: data.data });
        }
        if (data.type === "error") {
          error.value = data.message;
          poseReady = false;
        }
      };
      poseWorker.onerror = () => {
        frameBusy = false;
        error.value = "动作检测线程启动失败，摄像头仍可使用";
      };
      poseWorker.postMessage({ type: "init" });
      frameTimer = setInterval(async () => {
        if (!poseReady || frameBusy || !camera.value?.videoWidth) return;
        frameBusy = true;
        try {
          const image = await createImageBitmap(camera.value);
          poseWorker?.postMessage({ image, time: performance.now() }, [image]);
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
    }
  }
  function setVision() {
    send("vision_consent", { enabled: cloudVision.value });
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
