import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  AudioLines,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BookHeart,
  BrainCircuit,
  Check,
  CheckCheck,
  ChevronDown,
  ChevronRight,
  Clapperboard,
  Clock3,
  Cloud,
  FileText,
  Feather,
  Heart,
  Image,
  Layers3,
  LogIn,
  LogOut,
  ListTodo,
  Mic,
  Menu,
  Paintbrush2,
  Plus,
  Search,
  Save,
  Sparkles,
  Sun,
  Tag,
  UserRound,
  Wand2,
  X,
} from "lucide-react";
import {
  ApiError,
  apiRequest,
  type AccountProfile,
  type AccountUser,
  type ApiMemory,
  type ApiMood,
  type ApiTask,
} from "./auth";

type Mood = "Sunny" | "Soft" | "Focused" | "Cloudy" | "Restless";
type Memory = {
  id: string;
  title: string;
  date: string;
  text: string;
  mood: Mood;
  tag: string;
  color: string;
  sourceText?: string;
  result?: Record<string, unknown>;
  mode?: string;
  template?: JournalTemplate;
};
type JournalTemplate = "Soft pages" | "Scrapbook" | "Film diary";
type Task = {
  id: string;
  title: string;
  due: string;
  done: boolean;
  priority: "Gentle" | "Normal" | "Important";
};
type Page = "Home" | "AI studio" | "My memories" | "Little tasks" | "Mood garden" | "Vlog studio" | "Profile";
type Profile = {
  name: string;
  email: string;
  emailVerified: boolean;
  writingStyle: string;
  journalTone: string;
  interests: string;
  goals: string;
  preferredLanguage: string;
  timezone: string;
  reminderTime: string;
  emailNotifications: boolean;
  inAppNotifications: boolean;
  hasProfileImage: boolean;
  joinedAt: string;
};

type SpeechResultLike = { transcript: string };
type SpeechRecognitionEventLike = { results: ArrayLike<ArrayLike<SpeechResultLike>> };
type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

const today = new Date();
const dateKey = (date: Date) => date.toISOString().slice(0, 10);
const readableDate = (value: string) =>
  new Date(`${value}T12:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
const todayLabel = today.toLocaleDateString("en-US", {
  weekday: "long",
  month: "long",
  day: "numeric",
});

function profileFromApi(saved: AccountProfile, user: AccountUser): Profile {
  return {
    name: saved.full_name,
    email: saved.email,
    emailVerified: saved.email_verified,
    writingStyle: saved.writing_style,
    journalTone: saved.journal_tone,
    interests: saved.interests,
    goals: saved.goals,
    preferredLanguage: saved.preferred_language,
    timezone: saved.timezone,
    reminderTime: saved.reminder_time,
    emailNotifications: saved.email_notifications,
    inAppNotifications: saved.in_app_notifications,
    hasProfileImage: saved.has_profile_image,
    joinedAt: user.created_at.slice(0, 10),
  };
}

const moodOptions: { name: Mood; face: string; color: string }[] = [
  { name: "Sunny", face: "☀️", color: "mood-sun" },
  { name: "Soft", face: "🌷", color: "mood-soft" },
  { name: "Focused", face: "🌿", color: "mood-focus" },
  { name: "Cloudy", face: "☁️", color: "mood-cloud" },
  { name: "Restless", face: "✨", color: "mood-restless" },
];

function memoryFromApi(memory: ApiMemory): Memory {
  const savedDisplayText = memory.result.display_text;
  const generatedJournal = memory.result.journal;
  const savedTemplate = memory.result.journal_template;
  const mood = moodOptions.find((option) => option.name === memory.mood)?.name ?? "Soft";
  return {
    id: String(memory.id),
    title: memory.title,
    date: memory.memory_date,
    text: typeof savedDisplayText === "string" && savedDisplayText
      ? savedDisplayText
      : typeof generatedJournal === "string" && generatedJournal
        ? generatedJournal
        : memory.source_text,
    sourceText: memory.source_text,
    result: memory.result,
    mode: memory.mode,
    mood,
    tag: memory.tags.split(",").map((tag) => tag.trim()).find(Boolean) ?? "today",
    color: "lilac",
    ...(savedTemplate === "Soft pages" || savedTemplate === "Scrapbook" || savedTemplate === "Film diary"
      ? { template: savedTemplate }
      : {}),
  };
}

function taskFromApi(task: ApiTask): Task {
  const priority = task.priority === "high"
    ? "Important"
    : task.priority === "low"
      ? "Gentle"
      : "Normal";
  return {
    id: String(task.id),
    title: task.title,
    due: task.due_date ? readableDate(task.due_date) : "Whenever",
    done: task.completed,
    priority,
  };
}

function LifeLogMark() {
  return <span aria-hidden="true" className="brand-logo-mark">✦</span>;
}

function LandingPage({ onGetStarted, onPreview }: { onGetStarted: () => void; onPreview: () => void }) {
  return (
    <main className="landing-page">
      <header className="landing-nav">
        <a className="landing-brand" href="#landing-top"><span className="brand-mark"><LifeLogMark /></span><span>LifeLog <i>AI</i></span></a>
        <nav aria-label="Landing page navigation"><a href="#landing-workflow">Features</a><a href="#landing-how">How it works</a><a href="#landing-about">About</a></nav>
        <div className="landing-nav-actions"><button className="landing-signin" onClick={onGetStarted}>Sign in</button><button className="landing-get-started" onClick={onGetStarted}>Get started <ArrowRight size={15} /></button></div>
      </header>
      <section className="landing-hero" id="landing-top">
        <div className="landing-copy">
          <div className="landing-pill"><Sparkles size={13} /> YOUR AI JOURNAL & VLOG ASSISTANT</div>
          <h1>Speak your day.<br /><span>Live it again.</span></h1>
          <p>Turn voice notes, photos and everyday moments into journals, plans, reminders and creative stories.</p>
          <div className="landing-cta-row"><button className="landing-get-started landing-primary" onClick={onGetStarted}>Get started <ArrowRight size={16} /></button><button className="landing-watch" onClick={onPreview}><span>▶</span> See how it works</button></div>
          <div className="landing-proof"><span className="landing-avatar-stack"><i>M</i><i>✿</i><i>♡</i></span><span>A gentle space to keep your real, everyday stories.</span></div>
        </div>
        <div className="landing-art-wrap" role="img" aria-label="Anime-inspired scene of Mia journaling beside a sunset window">
          <div className="landing-art-glow" />
          <div className="landing-window"><div className="window-pane pane-one" /><div className="window-pane pane-two" /><div className="window-pane pane-three" /><div className="window-pane pane-four" /><div className="window-city city-back" /><div className="window-city city-front" /><div className="window-sun" /><span className="window-star star-one">✦</span><span className="window-star star-two">✧</span></div>
          <div className="landing-room"><div className="room-shelf"><i /><i /><i /><b /></div><div className="landing-desk" /><div className="landing-plant"><i /><i /><i /><b /></div><div className="landing-mug"><i /></div><div className="landing-book"><i /><i /><i /></div>
            <div className="anime-mia"><div className="mia-hair"><i /><i /><b /></div><div className="mia-face"><i /><i /><b /><em /></div><div className="mia-neck" /><div className="mia-body" /><div className="mia-arm" /><div className="mia-sleeve" /></div>
          </div>
          <div className="landing-art-label art-label-top"><span>✦</span> Capture your day</div><div className="landing-art-label art-label-bottom"><span>✿</span> Turn moments into stories</div>
          <div className="landing-note-card"><span className="note-card-icon"><AudioLines size={14} /></span><span><b>Your voice, remembered</b><small>Speech · Journal · You</small></span><Sparkles size={14} /></div>
        </div>
        <span className="landing-sparkle landing-sparkle-one">✧</span><span className="landing-sparkle landing-sparkle-two">✦</span>
      </section>
      <section className="landing-workflow" id="landing-workflow">
        <div className="landing-section-heading"><span>FROM A MOMENT TO A MEMORY</span><h2>A little help with your everyday.</h2><p>Capture it your way. Shape it into something you’ll want to keep.</p></div>
        <div className="landing-feature-grid">
          <article className="landing-feature-card feature-speech"><span className="landing-feature-icon"><Mic size={19} /></span><span className="feature-step">01 · CAPTURE</span><h3>Speech to text</h3><p>Talk through your day and turn your voice into an editable note.</p><span className="feature-visual voice-wave"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></span></article>
          <article className="landing-feature-card feature-journal"><span className="landing-feature-icon"><Wand2 size={19} /></span><span className="feature-step">02 · TRANSFORM</span><h3>Notes into stories</h3><p>Shape a rough note into a journal, reflection, caption or action list.</p><span className="feature-visual transform-visual"><span>your note</span><ArrowRight size={15} /><b>your story</b></span></article>
          <article className="landing-feature-card feature-memory"><span className="landing-feature-icon"><BookHeart size={19} /></span><span className="feature-step">03 · KEEP</span><h3>Memories, made yours</h3><p>Collect your favorite moments, small plans and daily thoughts in one cozy place.</p><span className="feature-visual memory-visual"><i>✿</i><i>☼</i><i>♡</i><i>✦</i></span></article>
        </div>
      </section>
      <section className="landing-how" id="landing-how"><span className="how-illustration">✿</span><div><span className="feature-step">A SMALL RITUAL, JUST FOR YOU</span><h2>Your day doesn’t need to be extraordinary to be worth remembering.</h2><p>LifeLog helps you notice the little things: what happened, how it felt, and what you want to carry into tomorrow.</p><button className="hero-link" onClick={onGetStarted}>Make space for your story <ArrowRight size={16} /></button></div></section>
      <footer className="landing-footer" id="landing-about"><span className="landing-brand"><span className="brand-mark"><LifeLogMark /></span><span>LifeLog <i>AI</i></span></span><span>Your day, beautifully remembered.</span><button onClick={onGetStarted}>Come on in <ArrowRight size={14} /></button></footer>
    </main>
  );
}

function App() {
  const [page, setPage] = useState<Page>("Home");
  const [showAuth, setShowAuth] = useState(false);
  const [profile, setProfile] = useState<Profile>({
    name: "Mia",
    email: "",
    emailVerified: false,
    writingStyle: "Reflective",
    journalTone: "Warm",
    interests: "",
    goals: "",
    preferredLanguage: "en",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
    reminderTime: "09:00",
    emailNotifications: true,
    inAppNotifications: true,
    hasProfileImage: false,
    joinedAt: new Date().toISOString().slice(0, 10),
  });
  const [session, setSession] = useState<AccountUser | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [accountDataStatus, setAccountDataStatus] = useState<"loading" | "ready" | "error">("loading");
  const [accountDataError, setAccountDataError] = useState("");
  const [accountDataReload, setAccountDataReload] = useState(0);
  const [authNotice, setAuthNotice] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [memories, setMemories] = useState<Memory[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [mood, setMood] = useState<Mood | null>(null);
  const [moodHistory, setMoodHistory] = useState<ApiMood[]>([]);
  const [query, setQuery] = useState("");
  const [composerOpen, setComposerOpen] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [taskDraft, setTaskDraft] = useState("");
  const [taskDueDate, setTaskDueDate] = useState("");
  const [taskReminderEnabled, setTaskReminderEnabled] = useState(false);
  const [memorySearchResults, setMemorySearchResults] = useState<Memory[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [vlogMemoryId, setVlogMemoryId] = useState("");
  const [vlogTemplate, setVlogTemplate] = useState("Soft storyboard");

  useEffect(() => {
    let active = true;
    const initialize = async () => {
      const params = new URLSearchParams(window.location.search);
      const verificationToken = params.get("verify");
      const currentResetToken = params.get("reset");
      if (verificationToken) {
        setShowAuth(true);
        try {
          const result = await apiRequest<{ message: string }>("/api/auth/verify-email", {
            method: "POST",
            body: JSON.stringify({ token: verificationToken }),
          });
          if (active) setAuthNotice(result.message);
        } catch (error) {
          if (active) setAuthNotice(error instanceof Error ? error.message : "Verification failed.");
        }
        params.delete("verify");
        window.history.replaceState({}, "", `${window.location.pathname}${params.size ? `?${params}` : ""}`);
      }
      if (currentResetToken) {
        setResetToken(currentResetToken);
        setShowAuth(true);
        params.delete("reset");
        window.history.replaceState({}, "", `${window.location.pathname}${params.size ? `?${params}` : ""}`);
      }
      try {
        const user = await apiRequest<AccountUser>("/api/auth/me");
        const savedProfile = await apiRequest<AccountProfile>("/api/profile");
        if (active) {
          setSession(user);
          setProfile(profileFromApi(savedProfile, user));
        }
      } catch (error) {
        if (error instanceof ApiError && error.status !== 401 && active) {
          setAuthNotice("The account service is unavailable. Start the API server and try again.");
        }
      } finally {
        if (active) setAuthReady(true);
      }
    };
    void initialize();
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    if (!session) {
      setMemories([]);
      setTasks([]);
      setMood(null);
      setMoodHistory([]);
      setAccountDataError("");
      setAccountDataStatus("ready");
      return () => { active = false; };
    }
    const loadAccountData = async () => {
      setAccountDataStatus("loading");
      setAccountDataError("");
      try {
        const [savedMemories, savedTasks, savedMoods] = await Promise.all([
          apiRequest<ApiMemory[]>("/api/memories"),
          apiRequest<ApiTask[]>("/api/tasks"),
          apiRequest<ApiMood[]>("/api/moods"),
        ]);
        if (!active) return;
        setMemories(savedMemories.map(memoryFromApi));
        setTasks(savedTasks.map(taskFromApi));
        setMoodHistory(savedMoods);
        const todayMood = savedMoods.find((entry) => entry.checkin_date === dateKey(new Date()));
        setMood(todayMood?.mood ?? null);
        setAccountDataStatus("ready");
      } catch (error) {
        if (active) {
          if (error instanceof ApiError && error.status === 401) {
            setSession(null);
            return;
          }
          setAccountDataError(error instanceof Error ? error.message : "Could not load your account data.");
          setAccountDataStatus("error");
        }
      }
    };
    void loadAccountData();
    return () => { active = false; };
  }, [session?.id, accountDataReload]);

  useEffect(() => {
    let active = true;
    if (!session || !query.trim()) {
      setMemorySearchResults(memories);
      return () => { active = false; };
    }
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ search: query.trim() });
      void apiRequest<ApiMemory[]>(`/api/memories?${params.toString()}`)
        .then((results) => {
          if (active) setMemorySearchResults(results.map(memoryFromApi));
        })
        .catch((error: unknown) => {
          if (active) showNotice(error instanceof Error ? error.message : "Memory search failed.");
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [memories, query, session?.id]);

  const filteredMemories = query.trim() ? memorySearchResults : memories;
  const unfinishedTasks = tasks.filter((task) => !task.done);
  const firstName = profile.name.trim().split(/\s+/)[0] || "Mia";
  const showNotice = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3200);
  };

  const addMemory = async (entry: Omit<Memory, "id" | "color">) => {
    const result = {
      ...(entry.result ?? {}),
      ...(entry.template ? { journal_template: entry.template } : {}),
    };
    const saved = await apiRequest<ApiMemory>("/api/memories", {
      method: "POST",
      body: JSON.stringify({
        title: entry.title,
        source_text: entry.sourceText ?? entry.text,
        memory_date: entry.date,
        tags: entry.tag,
        mood: entry.mood,
        mode: entry.mode ?? "Simple Journal",
        result,
      }),
    });
    setMemories((current) => [memoryFromApi(saved), ...current]);
    setComposerOpen(false);
    setPage("My memories");
    showNotice("Your little memory has been saved to your account ✨");
  };

  const addGeneratedMemory = async (
    title: string,
    text: string,
    sourceText: string,
    mode: string,
    result: Record<string, unknown>,
  ) => {
    await addMemory({
      title,
      date: dateKey(new Date()),
      text,
      sourceText,
      mood: mood ?? "Soft",
      tag: "AI studio",
      mode,
      result,
    });
  };

  const generateVlog = async (memoryId: string, template: string) => {
    const memory = memories.find((item) => item.id === memoryId);
    if (!memory) throw new Error("Choose one of your saved memories first.");
    const response = await apiRequest<{ result: Record<string, unknown> }>("/api/generation", {
      method: "POST",
      body: JSON.stringify({
        source_text: memory.sourceText ?? memory.text,
        mode: "Vlog Creator",
        output_length: "Medium",
        custom_prompt: `Format this as a ${template} storyboard. Keep the scenes and narration grounded only in this memory.`,
      }),
    });
    const structured = response.result.structured_vlog;
    if (typeof structured !== "object" || structured === null || Array.isArray(structured)) {
      throw new Error("The AI provider returned no usable storyboard.");
    }
    const storyboard = structured as Record<string, unknown>;
    const textOf = (value: unknown) => typeof value === "string" ? value.trim() : "";
    const listOf = (value: unknown) => Array.isArray(value)
      ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
      : [];
    const script = [
      textOf(storyboard.hook) && `HOOK\n${textOf(storyboard.hook)}`,
      ...listOf(storyboard.scenes).map((scene, index) => `SCENE ${index + 1}\n${scene}`),
      listOf(storyboard.voiceover).length
        ? `VOICEOVER\n${listOf(storyboard.voiceover).join("\n")}`
        : "",
      listOf(storyboard.b_roll).length
        ? `B-ROLL\n${listOf(storyboard.b_roll).map((item) => `• ${item}`).join("\n")}`
        : "",
      textOf(storyboard.closing) && `CLOSING\n${textOf(storyboard.closing)}`,
    ].filter(Boolean).join("\n\n");
    if (!script) throw new Error("The AI provider returned an empty storyboard.");

    const result = {
      ...memory.result,
      vlog_script: script,
      vlog_template: template,
      structured_vlog: storyboard,
    };
    const saved = await apiRequest<ApiMemory>(`/api/memories/${memoryId}`, {
      method: "PATCH",
      body: JSON.stringify({ result }),
    });
    setMemories((current) => current.map((item) =>
      item.id === memoryId ? memoryFromApi(saved) : item,
    ));
    return script;
  };

  const removeMemory = async (id: string) => {
    await apiRequest<{ message: string }>(`/api/memories/${id}`, { method: "DELETE" });
    setMemories((current) => current.filter((memory) => memory.id !== id));
    setSelectedMemory(null);
    showNotice("That memory has been removed from your account.");
  };

  const toggleTask = async (id: string) => {
    const task = tasks.find((item) => item.id === id);
    if (!task) return;
    const saved = await apiRequest<ApiTask>(`/api/tasks/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ completed: !task.done }),
    });
    setTasks((current) => current.map((item) => item.id === id ? taskFromApi(saved) : item));
  };

  const addTask = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const clean = taskDraft.trim();
    if (!clean) return;
    if (taskReminderEnabled && !taskDueDate) {
      showNotice("Choose a due date before enabling an email reminder.");
      return;
    }
    const saved = await apiRequest<ApiTask>("/api/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: clean,
        due_date: taskDueDate || null,
        reminder_enabled: taskReminderEnabled,
      }),
    });
    setTasks((current) => [taskFromApi(saved), ...current]);
    setTaskDraft("");
    setTaskDueDate("");
    setTaskReminderEnabled(false);
    showNotice("A new little step, ready when you are.");
  };

  const createSuggestedTasks = async (titles: string[]) => {
    const results = await Promise.allSettled(titles.map((title) =>
      apiRequest<ApiTask>("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),
    ));
    const saved: string[] = [];
    const failed: string[] = [];
    const createdTasks: Task[] = [];
    results.forEach((result, index) => {
      if (result.status === "fulfilled") {
        saved.push(titles[index]);
        createdTasks.push(taskFromApi(result.value));
      } else {
        failed.push(titles[index]);
      }
    });
    if (createdTasks.length) {
      setTasks((current) => [...createdTasks, ...current]);
    }
    return { saved, failed };
  };

  const saveMood = async (nextMood: Mood) => {
    const saved = await apiRequest<ApiMood>("/api/moods", {
      method: "PUT",
      body: JSON.stringify({ mood: nextMood, checkin_date: dateKey(new Date()) }),
    });
    setMood(nextMood);
    setMoodHistory((current) => [
      saved,
      ...current.filter((entry) => entry.checkin_date !== saved.checkin_date),
    ]);
  };

  const selectPage = (next: Page) => {
    setPage(next);
    setMobileNavOpen(false);
    setSearchOpen(false);
    setAccountMenuOpen(false);
  };

  const signIn = async (email: string, password: string, rememberMe: boolean) => {
    const user = await apiRequest<AccountUser>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, remember_me: rememberMe }),
    });
    const savedProfile = await apiRequest<AccountProfile>("/api/profile");
    setSession(user);
    setProfile(profileFromApi(savedProfile, user));
    setAccountDataStatus("loading");
    setAuthNotice("");
    setPage("Home");
    setShowAuth(false);
    showNotice(`Welcome to your little corner, ${user.full_name.split(/\s+/)[0]} ✨`);
  };

  const register = async (name: string, email: string, password: string, confirmPassword: string) => {
    const result = await apiRequest<{ message: string }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: name,
        email,
        password,
        confirm_password: confirmPassword,
      }),
    });
    return result.message;
  };

  const forgotPassword = async (email: string) => {
    const result = await apiRequest<{ message: string }>("/api/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    return result.message;
  };

  const resetPassword = async (token: string, password: string, confirmPassword: string) => {
    const result = await apiRequest<{ message: string }>("/api/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, password, confirm_password: confirmPassword }),
    });
    return result.message;
  };

  const resendVerification = async (email: string) => {
    const result = await apiRequest<{ message: string }>("/api/auth/resend-verification", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
    return result.message;
  };

  const saveProfile = async (updated: Profile) => {
    if (!session) throw new Error("Sign in to update your profile.");
    const saved = await apiRequest<AccountProfile>("/api/profile", {
      method: "PATCH",
      body: JSON.stringify({
        full_name: updated.name,
        preferred_language: updated.preferredLanguage,
        timezone: updated.timezone,
        writing_style: updated.writingStyle,
        journal_tone: updated.journalTone,
        interests: updated.interests,
        goals: updated.goals,
        reminder_time: updated.reminderTime,
        email_notifications: updated.emailNotifications,
        in_app_notifications: updated.inAppNotifications,
      }),
    });
    setProfile(profileFromApi(saved, session));
    showNotice("Your profile has been updated.");
  };

  const updateAvatar = async (file: File | null) => {
    if (!session) throw new Error("Sign in to update your profile image.");
    if (file) {
      const formData = new FormData();
      formData.append("file", file);
      const saved = await apiRequest<AccountProfile>("/api/profile/avatar", {
        method: "PUT",
        body: formData,
      });
      setProfile(profileFromApi(saved, session));
    } else {
      const saved = await apiRequest<AccountProfile>("/api/profile/avatar", { method: "DELETE" });
      setProfile(profileFromApi(saved, session));
    }
  };

  const signOut = async () => {
    let remoteLogoutFailed = false;
    try {
      await apiRequest<{ message: string }>("/api/auth/logout", { method: "POST" });
    } catch {
      remoteLogoutFailed = true;
    } finally {
      setSession(null);
      setPage("Home");
      setShowAuth(false);
      setAccountMenuOpen(false);
    }
    if (remoteLogoutFailed) {
      showNotice("Signed out in this browser, but the server could not confirm session removal.");
    }
  };

  if (!authReady) {
    return <main className="auth-page"><div className="auth-form-wrap">Opening your LifeLog…</div></main>;
  }

  if (!session) {
    return showAuth
      ? <SignInPage
          initialName={profile.name}
          initialNotice={authNotice}
          resetToken={resetToken}
          onSignIn={signIn}
          onRegister={register}
          onForgotPassword={forgotPassword}
          onResetPassword={resetPassword}
          onResendVerification={resendVerification}
          onBack={() => setShowAuth(false)}
        />
      : <LandingPage onGetStarted={() => setShowAuth(true)} onPreview={() => document.getElementById("landing-workflow")?.scrollIntoView({ behavior: "smooth" })} />;
  }

  if (accountDataStatus === "loading") {
    return <main className="auth-page"><div className="auth-form-wrap">Loading your saved LifeLog data…</div></main>;
  }
  if (accountDataStatus === "error") {
    return (
      <main className="auth-page">
        <div className="auth-form-wrap">
          <h2>Your account data could not be loaded.</h2>
          <p role="alert">{accountDataError}</p>
          <button className="auth-submit" onClick={() => setAccountDataReload((value) => value + 1)}>
            Try again
          </button>
          <button className="auth-back-link" onClick={() => void signOut()}>Sign out</button>
        </div>
      </main>
    );
  }

  const exportJournal = () => {
    const contents = memories
      .map((memory) => `${memory.title} — ${readableDate(memory.date)}\nMood: ${memory.mood}\n\n${memory.text}`)
      .join("\n\n---\n\n");
    const url = URL.createObjectURL(new Blob([contents], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "my-lifelog-memories.txt";
    link.click();
    URL.revokeObjectURL(url);
    showNotice("Your journal export is ready.");
  };

  return (
    <div className="app-shell">
      {mobileNavOpen && <button className="nav-scrim" aria-label="Close menu" onClick={() => setMobileNavOpen(false)} />}
      <aside className={`sidebar ${mobileNavOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><LifeLogMark /></div>
          <span className="brand-text">LifeLog AI</span>
          <button className="icon-button mobile-close" onClick={() => setMobileNavOpen(false)} aria-label="Close navigation"><X size={19} /></button>
        </div>
        <div className="workspace-label">YOUR LITTLE CORNER</div>
        <nav className="main-nav" aria-label="Main navigation">
          <NavButton label="Home" active={page === "Home"} icon={<Layers3 />} onClick={() => selectPage("Home")} />
          <NavButton label="AI studio" active={page === "AI studio"} icon={<Wand2 />} onClick={() => selectPage("AI studio")} />
          <NavButton label="My memories" active={page === "My memories"} icon={<BookHeart />} count={memories.length} onClick={() => selectPage("My memories")} />
          <NavButton label="Little tasks" active={page === "Little tasks"} icon={<ListTodo />} count={unfinishedTasks.length} onClick={() => selectPage("Little tasks")} />
          <NavButton label="Mood garden" active={page === "Mood garden"} icon={<Heart />} onClick={() => selectPage("Mood garden")} />
          <NavButton label="Vlog studio" active={page === "Vlog studio"} icon={<Clapperboard />} onClick={() => selectPage("Vlog studio")} />
        </nav>

        <div className="sidebar-divider" />
        <div className="sidebar-label-row"><span>YOUR SPACE</span><button aria-label="Add a space" className="tiny-button" onClick={() => showNotice("Your cozy corner is all yours.")}><Plus size={15} /></button></div>
        <button className="space-link" onClick={() => selectPage("My memories")}><span className="space-dot dot-lilac" /> Daily journal <span className="space-count">{memories.length}</span></button>
        <button className="space-link" onClick={() => selectPage("Mood garden")}><span className="space-dot dot-peach" /> Mood garden <span className="space-count">↗</span></button>

        <div className="sidebar-spacer" />
        <div className="buddy-card">
          <div className="buddy-sparkle sparkle-one">✦</div>
          <div className="buddy-sparkle sparkle-two">✧</div>
          <div className="buddy-avatar" aria-hidden="true">
            <div className="avatar-hair"><span /><span /></div>
            <div className="avatar-face"><i /><i /><b /><em /></div>
            <div className="avatar-bow">✿</div>
          </div>
          <div className="buddy-copy">
            <span className="buddy-kicker">YOUR STORY BUDDY</span>
            <strong>Your story buddy says hi!</strong>
            <span>Every little moment matters.</span>
          </div>
          <span className="buddy-heart">♡</span>
        </div>
        <button className="profile-chip" onClick={() => selectPage("Profile")}>
          <span className="profile-avatar">{profile.name.slice(0, 1).toUpperCase()}</span>
          <span className="profile-copy"><strong>{profile.name}</strong><small>View your profile</small></span>
          <UserRound size={17} />
        </button>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" onClick={() => setMobileNavOpen(true)} aria-label="Open menu"><Menu size={21} /></button>
          <div className="breadcrumb"><span>My little corner</span><ChevronRight size={14} /><strong>{page}</strong></div>
          <div className="top-actions">
            {searchOpen ? (
              <div className="top-search">
                <Search size={16} />
                <input autoFocus aria-label="Search your memories" placeholder="Find a memory..." value={query} onChange={(event) => { setQuery(event.target.value); setPage("My memories"); }} />
                <button aria-label="Close search" onClick={() => { setSearchOpen(false); setQuery(""); }}><X size={15} /></button>
              </div>
            ) : (
              <button className="top-icon" onClick={() => setSearchOpen(true)} aria-label="Search memories"><Search size={18} /></button>
            )}
            <button className="top-icon notification-button" onClick={() => showNotice(unfinishedTasks.length ? `You have ${unfinishedTasks.length} little steps waiting.` : "All caught up. Take a breath 🌱")} aria-label="Notifications"><Bell size={18} /><i /></button>
            <div className="account-menu-wrap">
              <button className="top-profile" aria-expanded={accountMenuOpen} onClick={() => setAccountMenuOpen((open) => !open)}><span>{profile.name.slice(0, 1).toUpperCase()}</span><ChevronDown size={14} /></button>
              {accountMenuOpen && <div className="account-menu"><div className="account-menu-person"><strong>{profile.name}</strong><span>{profile.email}</span></div><button onClick={() => selectPage("Profile")}><UserRound size={15} /> View profile</button><button onClick={signOut}><LogOut size={15} /> Sign out</button></div>}
            </div>
          </div>
        </header>

        <div className="page-content">
          {page === "Home" && (
            <HomePage
              firstName={firstName}
              memoryCount={memories.length}
              todayMemoryCount={memories.filter((memory) => memory.date === dateKey(new Date())).length}
              memories={memories}
              mood={mood}
              tasks={tasks}
              onMood={(nextMood) => {
                void saveMood(nextMood).catch((error: unknown) =>
                  showNotice(error instanceof Error ? error.message : "Could not save this mood check-in."),
                );
              }}
              onCreate={() => setComposerOpen(true)}
              onOpenMemory={setSelectedMemory}
              onNavigate={selectPage}
              onToggleTask={(id) => {
                void toggleTask(id).catch((error: unknown) =>
                  showNotice(error instanceof Error ? error.message : "Could not update this task."),
                );
              }}
            />
          )}
          {page === "AI studio" && (
            <AIStudioPage onSave={addGeneratedMemory} onCreateTasks={createSuggestedTasks} />
          )}
          {page === "My memories" && (
            <MemoriesPage memories={filteredMemories} query={query} onQuery={setQuery} onCreate={() => setComposerOpen(true)} onExport={exportJournal} onOpenMemory={setSelectedMemory} />
          )}
          {page === "Little tasks" && (
            <TasksPage
              tasks={tasks}
              draft={taskDraft}
              onDraft={setTaskDraft}
              dueDate={taskDueDate}
              onDueDate={(value) => {
                setTaskDueDate(value);
                if (!value) setTaskReminderEnabled(false);
              }}
              reminderEnabled={taskReminderEnabled}
              onReminderEnabled={setTaskReminderEnabled}
              onAdd={(event) => {
                void addTask(event).catch((error: unknown) =>
                  showNotice(error instanceof Error ? error.message : "Could not save this task."),
                );
              }}
              onToggle={(id) => {
                void toggleTask(id).catch((error: unknown) =>
                  showNotice(error instanceof Error ? error.message : "Could not update this task."),
                );
              }}
            />
          )}
          {page === "Mood garden" && (
            <MoodPage
              moodHistory={moodHistory}
              mood={mood}
              onMood={(nextMood) => {
                void saveMood(nextMood).catch((error: unknown) =>
                  showNotice(error instanceof Error ? error.message : "Could not save this mood check-in."),
                );
              }}
            />
          )}
          {page === "Vlog studio" && (
            <VlogStudio
              memories={memories}
              template={vlogTemplate}
              onTemplate={setVlogTemplate}
              memoryId={vlogMemoryId}
              onMemory={setVlogMemoryId}
              onGenerate={generateVlog}
            />
          )}
          {page === "Profile" && (
            <ProfilePage
              profile={profile}
              memoriesCount={memories.length}
              tasksCount={tasks.length}
              onSave={saveProfile}
              onUpdateAvatar={updateAvatar}
              onSignOut={signOut}
            />
          )}
        </div>
        <footer className="app-footer"><span>Made for your real, beautifully imperfect days.</span><span><Cloud size={13} /> Saved to your account</span></footer>
      </main>

      {composerOpen && <MemoryComposer onClose={() => setComposerOpen(false)} onSave={addMemory} />}
      {selectedMemory && <MemoryDetail memory={selectedMemory} onClose={() => setSelectedMemory(null)} onDelete={() => {
        void removeMemory(selectedMemory.id).catch((error: unknown) =>
          showNotice(error instanceof Error ? error.message : "Could not remove this memory."),
        );
      }} />}
      {notice && <div role="status" className="toast"><span className="toast-icon"><Check size={15} /></span>{notice}</div>}
    </div>
  );
}

function NavButton({ label, active, icon, count, onClick }: { label: string; active: boolean; icon: ReactNode; count?: number; onClick: () => void }) {
  return (
    <button className={`nav-item ${active ? "nav-active" : ""}`} onClick={onClick}>
      <span className="nav-icon">{icon}</span><span>{label}</span>{count !== undefined && <span className="nav-count">{count}</span>}
      {active && <span className="active-indicator" />}
    </button>
  );
}

function HomePage({ firstName, memoryCount, todayMemoryCount, memories, mood, tasks, onMood, onCreate, onOpenMemory, onNavigate, onToggleTask }: {
  firstName: string;
  memoryCount: number;
  todayMemoryCount: number;
  memories: Memory[];
  mood: Mood | null;
  tasks: Task[];
  onMood: (mood: Mood) => void;
  onCreate: () => void;
  onOpenMemory: (memory: Memory) => void;
  onNavigate: (page: Page) => void;
  onToggleTask: (id: string) => void;
}) {
  const recent = memories.slice(0, 2);
  const activeTasks = tasks.filter((task) => !task.done).slice(0, 3);
  const highlight = recent[0];
  return (
    <>
      <section className="dashboard-welcome">
        <div>
          <div className="eyebrow"><Sun size={14} /> {todayLabel.toUpperCase()}</div>
          <h1>Good day, <span>{firstName}.</span> <span className="wave-emoji">✦</span></h1>
          <p>Here’s a little look at your day, one moment at a time.</p>
        </div>
        <button className="create-button" onClick={onCreate}><Plus size={18} /> Write today’s story</button>
      </section>

      <section className="stat-grid" aria-label="Your LifeLog at a glance">
        <StatCard icon={<BookHeart />} label="Journal" value={`${todayMemoryCount} today`} note="your story, kept close" tone="stat-lilac" />
        <StatCard icon={<ListTodo />} label="Tasks" value={`${tasks.filter((task) => !task.done).length} pending`} note="small steps count" tone="stat-peach" />
        <StatCard icon={<Image />} label="Memories" value={`${memoryCount} saved`} note="little things, treasured" tone="stat-yellow" />
        <StatCard icon={<Heart />} label="Mood" value={mood ?? "Check in"} note={mood ? "thanks for sharing" : "how are you feeling?"} tone="stat-mint" />
      </section>

      <section className="dashboard-feature-grid">
        <article className="today-highlight panel">
          <div className="section-heading">
            <div><span className="section-kicker">TODAY’S HIGHLIGHT</span><h3>A day worth remembering</h3></div>
            <button className="text-action" onClick={() => highlight && onOpenMemory(highlight)}>View details <ArrowRight size={14} /></button>
          </div>
          {highlight ? (
            <button className="highlight-memory" onClick={() => onOpenMemory(highlight)}>
              <MemoryArtwork memory={highlight} />
              <span className="highlight-copy"><span className="highlight-date">{readableDate(highlight.date)} · {highlight.mood.toLowerCase()} day</span><strong>{highlight.title}</strong><span>{highlight.text}</span><span className="highlight-tag"><Tag size={12} /> {highlight.tag}</span></span>
            </button>
          ) : <button className="highlight-empty" onClick={onCreate}><Plus size={17} /> Add your first little moment</button>}
        </article>
        <article className="quick-actions-panel panel">
          <div className="section-heading"><div><span className="section-kicker">MAKE SOMETHING OF TODAY</span><h3>Quick actions</h3></div><Sparkles size={17} className="quick-action-sparkle" /></div>
          <button className="quick-action-row action-primary" onClick={() => onNavigate("AI studio")}><span className="quick-action-icon"><Mic size={17} /></span><span><strong>Add a voice note</strong><small>Speak it, then shape it into a story</small></span><ArrowUpRight size={15} /></button>
          <button className="quick-action-row" onClick={onCreate}><span className="quick-action-icon"><Image size={17} /></span><span><strong>Write a memory</strong><small>Keep a moment from your day</small></span><ArrowUpRight size={15} /></button>
          <button className="quick-action-row" onClick={() => onNavigate("AI studio")}><span className="quick-action-icon"><Wand2 size={17} /></span><span><strong>Transform a note</strong><small>Explore journal and reflection drafts</small></span><ArrowUpRight size={15} /></button>
          <div className="mood-inline">
            <span>Today I feel</span>
            <div className="mood-options">
              {moodOptions.map((option) => <button key={option.name} title={option.name} aria-label={`I feel ${option.name}`} aria-pressed={mood === option.name} className={`mood-option ${mood === option.name ? "mood-selected" : ""}`} onClick={() => onMood(option.name)}><span className={`mood-face ${option.color}`}>{option.face}</span></button>)}
            </div>
          </div>
        </article>
      </section>

      <section className="dashboard-lower-grid">
        <div className="recent-section dashboard-recent">
          <div className="section-heading recent-heading">
            <div><span className="section-kicker">KEPT CLOSE</span><h3>Recent little moments</h3></div>
            <button className="text-action" onClick={() => onNavigate("My memories")}>View all <ArrowRight size={14} /></button>
          </div>
          <div className="memory-grid dashboard-memory-grid">
            {recent.map((memory, index) => <MemoryCard key={memory.id} memory={memory} index={index} onOpen={() => onOpenMemory(memory)} />)}
            <button className="new-memory-card" onClick={onCreate}><span className="new-memory-icon"><Plus size={20} /></span><strong>One more story<br />starts right here.</strong><span>Save a small moment <ArrowRight size={14} /></span><span className="new-memory-doodle">✿</span></button>
          </div>
        </div>
        <article className="tasks-panel panel dashboard-tasks">
          <div className="section-heading"><div><span className="section-kicker">GENTLE REMINDERS</span><h3>Little next steps</h3></div><button className="text-action" onClick={() => onNavigate("Little tasks")}>See all <ArrowRight size={14} /></button></div>
          <div className="task-list">{activeTasks.length ? activeTasks.map((task) => <label className="task-row" key={task.id}><button className="task-check" aria-label={`Mark ${task.title} complete`} onClick={() => onToggleTask(task.id)}><Check size={13} /></button><span className="task-title">{task.title}</span><span className={`task-due ${task.priority === "Important" ? "due-today" : ""}`}>{task.due}</span></label>) : <div className="empty-mini"><CheckCheck size={18} /> All your little steps are done. Nice work!</div>}</div>
          <button className="add-task-link" onClick={() => onNavigate("Little tasks")}><Plus size={15} /> Add a tiny task</button>
        </article>
      </section>
    </>
  );
}

function StatCard({ icon, label, value, note, tone }: { icon: ReactNode; label: string; value: string; note: string; tone: string }) {
  return <div className={`stat-card ${tone}`}><div className="stat-top"><span className="stat-icon">{icon}</span><span className="stat-label">{label}</span><ArrowDownRight className="stat-arrow" size={15} /></div><div className="stat-value">{value}</div><div className="stat-note">{note}</div></div>;
}

function MemoryArtwork({ memory }: { memory: Memory }) {
  return <div className={`memory-art highlight-art memory-${memory.color}`} aria-hidden="true"><span className="memory-art-date">{readableDate(memory.date)}</span><div className="memory-art-sun" /><div className="scenery highlight-scenery"><span className="scene-sparkle">✦</span><span className="scene-window" /><span className="scene-person"><i /><b /></span><span className="scene-desk" /></div><span className="memory-art-caption">a little scene from today</span></div>;
}

function MemoryCard({ memory, index = 0, onOpen }: { memory: Memory; index?: number; onOpen: () => void }) {
  return (
    <article className={`memory-card memory-${memory.color} memory-card-${index} ${memory.template ? `journal-${memory.template.toLowerCase().replaceAll(" ", "-")}` : ""}`} style={{ animationDelay: `${Math.min(index, 6) * 55}ms` }}>
      <div className="memory-art">
        <span className="memory-art-date">{readableDate(memory.date)}</span>
        <div className="memory-art-sun" />
        {memory.color === "peach" ? <div className="scenery bakery"><div className="scenery-roof" /><div className="scenery-window" /><div className="scenery-door" /><span className="sign">BAKE</span></div> : null}
        {memory.color === "lavender" ? <div className="scenery night-sky"><span className="moon">☾</span><span className="sky-star">✦</span><span className="sky-star">✧</span><div className="book-stack"><i /><i /><i /></div></div> : null}
        {memory.color === "sage" ? <div className="scenery rainy"><span className="rain-drop">⌁</span><span className="rain-drop">⌁</span><span className="rain-drop">⌁</span><div className="tea-cup">☕</div><div className="window-sill" /></div> : null}
        {memory.color === "lilac" ? <div className="scenery new-scene"><span>✿</span><span>✧</span><span>♡</span></div> : null}
        <span className="memory-art-caption">{memory.mood === "Sunny" ? "a golden little day" : memory.mood === "Soft" ? "a soft place to land" : "one step, then another"}</span>
      </div>
      <div className="memory-card-copy">
        <div className="memory-card-meta"><span><span className="tiny-heart">♡</span> {readableDate(memory.date)}</span><span className="memory-tag"><Tag size={11} /> {memory.tag}</span></div>
        <h4>{memory.title}</h4>
        <p>{memory.text}</p>
        <div className="memory-card-bottom"><span className="memory-mood">{moodOptions.find((option) => option.name === memory.mood)?.face} {memory.mood}</span><button aria-label={`Open ${memory.title}`} onClick={onOpen}><ArrowRight size={16} /></button></div>
      </div>
    </article>
  );
}

function MemoriesPage({ memories, query, onQuery, onCreate, onExport, onOpenMemory }: { memories: Memory[]; query: string; onQuery: (query: string) => void; onCreate: () => void; onExport: () => void; onOpenMemory: (memory: Memory) => void }) {
  return (
    <>
      <div className="page-heading-row"><div><div className="eyebrow"><BookHeart size={14} /> YOUR STORY SO FAR</div><h1>My <span>memories.</span></h1><p>A little shelf for the days you don’t want to lose.</p></div><button className="create-button" onClick={onCreate}><Plus size={18} /> Add a memory</button></div>
      <div className="library-toolbar"><label className="library-search"><Search size={17} /><input placeholder="Search a feeling, a place, a little detail..." value={query} onChange={(event) => onQuery(event.target.value)} /><kbd>⌘ K</kbd></label><button className="outline-button" onClick={onExport}><ArrowRight size={15} /> Export journal</button></div>
      <div className="library-note"><Sparkles size={15} /><span>Your memories are saved privately to your account.</span><span className="library-sort">Most recent <ChevronDown size={14} /></span></div>
      {memories.length ? <div className="library-grid">{memories.map((memory, index) => <MemoryCard key={memory.id} memory={memory} index={index} onOpen={() => onOpenMemory(memory)} />)}</div> : <div className="empty-state"><span className="empty-illustration">✿</span><h3>No moments found just yet.</h3><p>Try a different search, or save a new little story.</p><button className="create-button" onClick={onCreate}><Plus size={17} /> Write a memory</button></div>}
    </>
  );
}

function TasksPage({
  tasks,
  draft,
  onDraft,
  dueDate,
  onDueDate,
  reminderEnabled,
  onReminderEnabled,
  onAdd,
  onToggle,
}: {
  tasks: Task[];
  draft: string;
  onDraft: (value: string) => void;
  dueDate: string;
  onDueDate: (value: string) => void;
  reminderEnabled: boolean;
  onReminderEnabled: (enabled: boolean) => void;
  onAdd: (event: FormEvent<HTMLFormElement>) => void;
  onToggle: (id: string) => void;
}) {
  const pending = tasks.filter((task) => !task.done);
  const complete = tasks.filter((task) => task.done);
  return (
    <>
      <div className="page-heading-row"><div><div className="eyebrow"><ListTodo size={14} /> ONE THING AT A TIME</div><h1>Little <span>next steps.</span></h1><p>They don’t have to be big to move you forward.</p></div><div className="task-count-bubble"><span>{pending.length}</span><small>still waiting<br />when you’re ready</small></div></div>
      <form className="add-task-form" onSubmit={onAdd}>
        <span className="add-task-plus"><Plus size={17} /></span>
        <input aria-label="Add a task" placeholder="What’s one little thing you’d like to do?" value={draft} onChange={(event) => onDraft(event.target.value)} />
        <input className="task-date-field" type="date" aria-label="Optional due date" value={dueDate} onChange={(event) => onDueDate(event.target.value)} />
        <label className="task-reminder-toggle" title={dueDate ? "Send an email reminder at your profile reminder time." : "Choose a due date to enable email reminders."}>
          <input type="checkbox" checked={reminderEnabled} disabled={!dueDate} onChange={(event) => onReminderEnabled(event.target.checked)} />
          Email reminder
        </label>
        <button type="submit"><Plus size={16} /> Add task</button>
      </form>
      <div className="task-page-columns"><section className="task-page-panel"><div className="section-heading"><div><span className="section-kicker">ON YOUR MIND</span><h3>Whenever you’re ready</h3></div><span className="pill-count">{pending.length} open</span></div>{pending.length ? pending.map((task) => <TaskPageRow key={task.id} task={task} onToggle={onToggle} />) : <div className="empty-mini"><CheckCheck size={18} /> Nothing waiting for you. Take a breath.</div>}</section>
        <section className="task-page-panel completed-panel"><div className="section-heading"><div><span className="section-kicker">LOOK AT YOU GO</span><h3>Little wins</h3></div><span className="pill-count completed-count">{complete.length} done</span></div>{complete.length ? complete.map((task) => <TaskPageRow key={task.id} task={task} onToggle={onToggle} />) : <p className="quiet-copy">Your wins will show up here.</p>}</section></div>
      <div className="kind-reminder"><span>🌱</span><div><strong>A gentle reminder</strong><p>Rest is productive, too. You can move a task to tomorrow, or let it go.</p></div></div>
    </>
  );
}

function TaskPageRow({ task, onToggle }: { task: Task; onToggle: (id: string) => void }) {
  return <div className={`task-page-row ${task.done ? "task-done" : ""}`}><button className="task-check" aria-label={`${task.done ? "Uncheck" : "Complete"} ${task.title}`} onClick={() => onToggle(task.id)}>{task.done && <Check size={13} />}</button><div className="task-page-copy"><strong>{task.title}</strong><span><Clock3 size={12} /> {task.due}</span></div><span className={`priority-dot priority-${task.priority.toLowerCase()}`} title={`${task.priority} priority`} /></div>;
}

function MoodPage({ moodHistory, mood, onMood }: { moodHistory: ApiMood[]; mood: Mood | null; onMood: (mood: Mood) => void }) {
  const moodCounts = moodOptions.map((option) => ({ ...option, count: moodHistory.filter((entry) => entry.mood === option.name).length }));
  return (
    <>
      <div className="page-heading-row"><div><div className="eyebrow"><Heart size={14} /> A KIND CHECK-IN</div><h1>Your mood <span>garden.</span></h1><p>Feelings are weather, not a forecast of who you are.</p></div><div className="garden-sticker">♡</div></div>
      <section className="mood-checkin-card"><div className="mood-checkin-copy"><span className="section-kicker">TODAY, RIGHT NOW</span><h2>How are you feeling<br />in this moment?</h2><p>You can change your answer whenever you like.</p></div><div className="mood-options mood-options-large">{moodOptions.map((option) => <button key={option.name} className={`mood-option ${mood === option.name ? "mood-selected" : ""}`} onClick={() => onMood(option.name)} aria-pressed={mood === option.name}><span className={`mood-face ${option.color}`}>{option.face}</span><span>{option.name}</span></button>)}</div></section>
      <section className="panel garden-panel"><div className="section-heading"><div><span className="section-kicker">NOT A SCORECARD</span><h3>Feelings you’ve made room for</h3></div><span className="garden-flower">✿</span></div><p className="panel-intro">Just little check-ins, gathered gently. There’s no good or bad mood here.</p><div className="mood-count-grid">{moodCounts.map((option) => <div key={option.name} className={`mood-count-card ${option.color}`}><span>{option.face}</span><strong>{String(option.count).padStart(2, "0")}</strong><small>{option.name.toLowerCase()} day{option.count === 1 ? "" : "s"}</small></div>)}</div></section>
      <div className="kind-reminder"><span>💌</span><div><strong>A gentle note</strong><p>Whatever you feel today, you don’t have to earn your way into being cared for.</p></div><span className="buddy-signoff">you’re doing fine ♡</span></div>
    </>
  );
}

function ProfilePage({ profile, memoriesCount, tasksCount, onSave, onUpdateAvatar, onSignOut }: {
  profile: Profile;
  memoriesCount: number;
  tasksCount: number;
  onSave: (profile: Profile) => Promise<void>;
  onUpdateAvatar: (file: File | null) => Promise<void>;
  onSignOut: () => Promise<void>;
}) {
  const [draft, setDraft] = useState(profile);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const update = <K extends keyof Profile>(field: K, value: Profile[K]) => {
    setDraft((current) => ({ ...current, [field]: value }));
  };
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onSave(draft);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your profile.");
    } finally {
      setBusy(false);
    }
  };
  const uploadAvatar = async (file: File | null) => {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      await onUpdateAvatar(file);
      update("hasProfileImage", true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update your profile image.");
    } finally {
      setBusy(false);
    }
  };
  const removeAvatar = async () => {
    setBusy(true);
    setError("");
    try {
      await onUpdateAvatar(null);
      update("hasProfileImage", false);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove your profile image.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading-row"><div><div className="eyebrow"><UserRound size={14} /> YOUR LITTLE CORNER</div><h1>Your <span>profile.</span></h1><p>A few details to make this space feel like yours.</p></div><button className="signout-button" onClick={() => void onSignOut()}><LogOut size={15} /> Sign out</button></div>
      <section className="profile-hero-card">
        <div className="profile-large-avatar">
          {draft.hasProfileImage
            ? <img src="/api/profile/avatar" alt="Your profile" />
            : draft.name.trim().slice(0, 1).toUpperCase() || "M"}
          <span>✿</span>
        </div>
        <div className="profile-hero-copy"><span className="section-kicker">THIS IS YOUR STORY</span><h2>{draft.name || "Your name"}</h2><p>{draft.goals || "A little space that’s all yours."}</p><span className="profile-joined"><Sun size={13} /> Here since {readableDate(profile.joinedAt)}</span></div><span className="profile-hero-doodle">♡</span>
      </section>
      <div className="profile-layout">
        <form className="profile-form panel" onSubmit={(event) => void save(event)}>
          <div className="section-heading"><div><span className="section-kicker">THE LITTLE DETAILS</span><h3>Make yourself at home</h3></div><Paintbrush2 size={18} className="profile-form-icon" /></div>
          <label className="field-label" htmlFor="profile-name">Full name</label>
          <input id="profile-name" className="profile-field" value={draft.name} onChange={(event) => update("name", event.target.value)} maxLength={120} required />
          <label className="field-label" htmlFor="profile-email">Email address <span>{profile.emailVerified ? "verified" : "not verified"}</span></label>
          <input id="profile-email" className="profile-field" type="email" value={draft.email} readOnly aria-readonly="true" />
          <label className="field-label" htmlFor="profile-language">Preferred language</label>
          <input id="profile-language" className="profile-field" value={draft.preferredLanguage} onChange={(event) => update("preferredLanguage", event.target.value)} placeholder="en or en-US" required />
          <label className="field-label" htmlFor="profile-timezone">Time zone</label>
          <input id="profile-timezone" className="profile-field" value={draft.timezone} onChange={(event) => update("timezone", event.target.value)} placeholder="Asia/Kolkata" required />
          <label className="field-label" htmlFor="profile-style">Writing style</label>
          <select id="profile-style" className="profile-field" value={draft.writingStyle} onChange={(event) => update("writingStyle", event.target.value)}><option>Reflective</option><option>Concise</option><option>Detailed</option><option>Conversational</option></select>
          <label className="field-label" htmlFor="profile-tone">Journal tone</label>
          <select id="profile-tone" className="profile-field" value={draft.journalTone} onChange={(event) => update("journalTone", event.target.value)}><option>Warm</option><option>Calm</option><option>Honest</option><option>Professional</option></select>
          <label className="field-label" htmlFor="profile-interests">Interests</label>
          <textarea id="profile-interests" className="profile-field profile-bio-field" rows={3} maxLength={2000} value={draft.interests} onChange={(event) => update("interests", event.target.value)} />
          <label className="field-label" htmlFor="profile-goals">Goals</label>
          <textarea id="profile-goals" className="profile-field profile-bio-field" rows={3} maxLength={2000} value={draft.goals} onChange={(event) => update("goals", event.target.value)} />
          <label className="field-label" htmlFor="profile-reminder">Preferred reminder time</label>
          <input id="profile-reminder" className="profile-field" type="time" value={draft.reminderTime} onChange={(event) => update("reminderTime", event.target.value)} required />
          <label className="profile-notification-option"><input type="checkbox" checked={draft.emailNotifications} onChange={(event) => update("emailNotifications", event.target.checked)} /> Email notifications</label>
          <label className="profile-notification-option"><input type="checkbox" checked={draft.inAppNotifications} onChange={(event) => update("inAppNotifications", event.target.checked)} /> In-app notifications</label>
          <label className="field-label" htmlFor="profile-avatar">Profile image (JPEG, PNG, or WebP; up to 5 MB)</label>
          <input id="profile-avatar" className="profile-field" type="file" accept="image/jpeg,image/png,image/webp" disabled={busy} onChange={(event) => void uploadAvatar(event.target.files?.[0] ?? null)} />
          {draft.hasProfileImage && <button className="auth-back-link" type="button" disabled={busy} onClick={() => void removeAvatar()}>Remove profile image</button>}
          {error && <span className="auth-error" role="alert">{error}</span>}
          <div className="profile-form-footer"><span>Profile changes are saved to your account.</span><button type="submit" className="create-button" disabled={busy}><Save size={15} /> {busy ? "Saving…" : "Save profile"}</button></div>
        </form>
        <aside className="profile-side-column">
          <div className="profile-stats-card"><span className="section-kicker">YOUR LITTLE UNIVERSE</span><div className="profile-stat-row"><BookHeart size={16} /><span>Moments collected</span><strong>{memoriesCount}</strong></div><div className="profile-stat-row"><ListTodo size={16} /><span>Little next steps</span><strong>{tasksCount}</strong></div><div className="profile-kind-note">“You are allowed to be a work in progress and still be proud of yourself.”</div></div>
          <div className="profile-local-note"><Cloud size={16} /><div><strong>Connected features</strong><p>Your profile, memories, tasks, and mood check-ins are stored in the account database. AI and email need provider credentials in the backend environment.</p></div></div>
        </aside>
      </div>
    </>
  );
}

type AuthMode = "login" | "register" | "forgot" | "reset";

function SignInPage({ initialName, initialNotice, resetToken, onSignIn, onRegister, onForgotPassword, onResetPassword, onResendVerification, onBack }: {
  initialName: string;
  initialNotice: string;
  resetToken: string;
  onSignIn: (email: string, password: string, rememberMe: boolean) => Promise<void>;
  onRegister: (name: string, email: string, password: string, confirmPassword: string) => Promise<string>;
  onForgotPassword: (email: string) => Promise<string>;
  onResetPassword: (token: string, password: string, confirmPassword: string) => Promise<string>;
  onResendVerification: (email: string) => Promise<string>;
  onBack: () => void;
}) {
  const [name, setName] = useState(initialName || "");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [mode, setMode] = useState<AuthMode>(resetToken ? "reset" : "login");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState(initialNotice);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      if (mode === "register") {
        setNotice(await onRegister(name, email, password, confirmPassword));
        setMode("login");
        setPassword("");
        setConfirmPassword("");
      } else if (mode === "forgot") {
        setNotice(await onForgotPassword(email));
      } else if (mode === "reset") {
        setNotice(await onResetPassword(resetToken, password, confirmPassword) as string);
        setMode("login");
        setPassword("");
        setConfirmPassword("");
      } else {
        await onSignIn(email, password, rememberMe);
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The request could not be completed.");
    } finally {
      setBusy(false);
    }
  };

  const resendVerification = async () => {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      setNotice(await onResendVerification(email));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not send a verification link.");
    } finally {
      setBusy(false);
    }
  };
  const isRegister = mode === "register";
  const isReset = mode === "reset";
  const showPassword = mode === "login" || isRegister || isReset;
  const title = isRegister ? "Let’s make this yours." : mode === "forgot" ? "A fresh start." : isReset ? "Choose a new password." : "Welcome back.";
  const subtitle = isRegister
    ? "Create your account and verify your email to begin."
    : mode === "forgot"
      ? "We’ll send a reset link if a verified account matches."
      : isReset
        ? "Choose a strong password you have not used here before."
        : "Your little moments have been waiting for you.";

  return (
    <main className="auth-page">
      <section className="auth-art">
        <button className="auth-brand" onClick={onBack}><span className="brand-mark"><LifeLogMark /></span> <span className="brand-text">LifeLog AI</span></button>
        <div className="auth-scenery"><span className="auth-sun" /><span className="auth-moon">✦</span><div className="auth-person"><i /><b /><em /></div><div className="auth-journal"><span>dear diary...</span><i>♡</i></div><span className="auth-flower flower-one">✿</span><span className="auth-flower flower-two">✿</span><span className="auth-stars">✧　✦</span></div>
        <div className="auth-art-copy"><span>A SOFTER PLACE TO LAND</span><h1>Your story is<br />worth keeping.</h1><p>Make room for all the little things that make you, you.</p></div>
      </section>
      <section className="auth-form-side">
        <div className="auth-form-wrap">
          <button className="auth-back-link" onClick={onBack}><ArrowRight size={14} className="back-arrow" /> Back to LifeLog</button>
          <div className="auth-mobile-brand"><span className="brand-mark"><BookHeart size={18} /></span> LifeLog <i>AI</i></div>
          <div className="auth-kicker"><Sparkles size={14} /> YOUR OWN LITTLE CORNER</div>
          <h2>{title}</h2>
          <p className="auth-subtitle">{subtitle}</p>
          <form className="auth-form" onSubmit={(event) => void submit(event)}>
            {isRegister && <label>Full name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Alex Morgan" autoComplete="name" maxLength={120} required /></label>}
            <label>Email address<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" autoComplete="email" required /></label>
            {showPassword && <label>{isReset ? "New password" : "Password"}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete={isRegister || isReset ? "new-password" : "current-password"} minLength={isRegister || isReset ? 12 : undefined} required /></label>}
            {(isRegister || isReset) && <label>Confirm password<input type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={12} required /></label>}
            {isRegister && <small className="auth-help">Use at least 12 characters with three character types: lowercase, uppercase, number, and symbol.</small>}
            {mode === "login" && <label className="profile-notification-option"><input type="checkbox" checked={rememberMe} onChange={(event) => setRememberMe(event.target.checked)} /> Remember me on this device</label>}
            {notice && <span className="auth-success" role="status">{notice}</span>}
            {error && <span className="auth-error" role="alert">{error}</span>}
            {error.toLowerCase().includes("verify your email") && <button className="auth-back-link" type="button" disabled={busy} onClick={() => void resendVerification()}>Resend verification link</button>}
            <button className="auth-submit" type="submit" disabled={busy}>
              <LogIn size={16} /> {busy ? "Please wait…" : isRegister ? "Create account" : mode === "forgot" ? "Send reset link" : isReset ? "Reset password" : "Sign in"} <ArrowRight size={16} />
            </button>
          </form>
          {mode === "login" && <div className="auth-toggle"><button onClick={() => { setMode("forgot"); setError(""); setNotice(""); }}>Forgot password?</button></div>}
          {(mode === "login" || isRegister) && <div className="auth-toggle">{isRegister ? "Already have an account?" : "New around here?"}<button onClick={() => { setMode(isRegister ? "login" : "register"); setError(""); setNotice(""); }}>{isRegister ? "Sign in" : "Create an account"}</button></div>}
          {mode === "forgot" && <div className="auth-toggle">Remembered your password?<button onClick={() => { setMode("login"); setError(""); }}>Sign in</button></div>}
          <div className="auth-demo-note"><Heart size={14} /><span>Account sessions, profile settings, memories, tasks, and mood check-ins are managed by the server.</span></div>
        </div>
      </section>
    </main>
  );
}

type TransformMode =
  | "Simple Journal"
  | "Personal Persona"
  | "Structured Day"
  | "Reflection"
  | "Explain Through an Analogy"
  | "Vlog Creator"
  | "Social Media"
  | "Custom Prompt";

function formatGenerationOutput(mode: TransformMode, result: Record<string, unknown>) {
  const record = (value: unknown): Record<string, unknown> =>
    typeof value === "object" && value !== null && !Array.isArray(value)
      ? value as Record<string, unknown>
      : {};
  const formatValue = (value: unknown) => {
    if (typeof value === "string") return value.trim();
    if (Array.isArray(value)) {
      return value
        .filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
        .map((item) => `• ${item.trim()}`)
        .join("\n");
    }
    return "";
  };
  const formatSections = (source: Record<string, unknown>, fields: [string, string][]) =>
    fields
      .map(([label, key]) => {
        const content = formatValue(source[key]);
        return content ? `${label}\n${content}` : "";
      })
      .filter(Boolean)
      .join("\n\n");

  if (mode === "Simple Journal" || mode === "Personal Persona") {
    return formatValue(result.journal);
  }
  if (mode === "Reflection") return formatValue(result.reflection);
  if (mode === "Structured Day") {
    return formatSections(record(result.structured_day), [
      ["Date", "date"],
      ["Summary", "summary"],
      ["Events", "events"],
      ["Achievements", "achievements"],
      ["Challenges", "challenges"],
      ["Mood", "mood"],
      ["Completed tasks", "completed_tasks"],
      ["Pending tasks", "pending_tasks"],
      ["Future plans", "future_plans"],
      ["Important moments", "important_moments"],
    ]);
  }
  if (mode === "Explain Through an Analogy") {
    return formatSections(record(result.structured_analogy), [
      ["Analogy", "analogy"],
      ["Mapping", "mapping"],
      ["Simpler version", "simpler_version"],
      ["More detail", "detailed_version"],
    ]);
  }
  if (mode === "Vlog Creator") {
    return formatSections(record(result.structured_vlog), [
      ["Title", "title"],
      ["Hook", "hook"],
      ["Scenes", "scenes"],
      ["Voice-over", "voiceover"],
      ["B-roll", "b_roll"],
      ["Closing", "closing"],
    ]);
  }
  if (mode === "Social Media") {
    return formatSections(record(result.structured_social), [
      ["Caption", "caption"],
      ["Alternatives", "alternatives"],
      ["Hashtags", "hashtags"],
      ["Story", "story_text"],
    ]);
  }
  return (
    formatValue(result.journal) ||
    formatValue(result.reflection) ||
    formatValue(result.vlog_script)
  );
}

function AIStudioPage({ onSave, onCreateTasks }: {
  onSave: (
    title: string,
    text: string,
    sourceText: string,
    mode: string,
    result: Record<string, unknown>,
  ) => Promise<void>;
  onCreateTasks: (titles: string[]) => Promise<{ saved: string[]; failed: string[] }>;
}) {
  const [note, setNote] = useState("");
  const [voiceText, setVoiceText] = useState("");
  const [mode, setMode] = useState<TransformMode>("Simple Journal");
  const [customPrompt, setCustomPrompt] = useState("");
  const [output, setOutput] = useState("");
  const [status, setStatus] = useState("Generated content uses the configured AI provider. Browser speech recognition is optional.");
  const [isListening, setIsListening] = useState(false);
  const [hasOutput, setHasOutput] = useState(false);
  const [busy, setBusy] = useState(false);
  const [generationResult, setGenerationResult] = useState<Record<string, unknown>>({});
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const fullNote = [note.trim(), voiceText.trim()].filter(Boolean).join("\n");

  useEffect(() => () => recognitionRef.current?.stop(), []);

  const startListening = () => {
    const speechWindow = window as SpeechWindow;
    const SpeechRecognition = speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setStatus("Speech recognition isn’t available in this browser. You can still type or paste your note.");
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.lang = navigator.language || "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      setVoiceText(Array.from(event.results).map((result) => result[0]?.transcript ?? "").join(" ").trim());
    };
    recognition.onerror = (event) => {
      setIsListening(false);
      setStatus(`Voice capture stopped: ${event.error}. Check your microphone permission and try again.`);
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setIsListening(false);
      setStatus("Voice capture ended. Review and edit the transcript before using it.");
    };
    try {
      recognitionRef.current = recognition;
      recognition.start();
      setIsListening(true);
      setStatus("Listening… speak naturally. You can edit the transcript at any time.");
    } catch (error) {
      recognitionRef.current = null;
      setIsListening(false);
      setStatus(`Couldn’t start voice capture${error instanceof Error ? `: ${error.message}` : "."}`);
    }
  };

  const stopListening = () => {
    recognitionRef.current?.stop();
    setIsListening(false);
  };

  const transformNote = async () => {
    const source = fullNote.trim();
    if (!source) {
      setStatus("Add a note or record your voice before creating a draft.");
      setHasOutput(false);
      return;
    }
    if (mode === "Custom Prompt" && !customPrompt.trim()) {
      setStatus("Add custom instructions before creating this draft.");
      setHasOutput(false);
      return;
    }

    setBusy(true);
    setHasOutput(false);
    setStatus("Sending your note to the configured AI provider…");
    try {
      const response = await apiRequest<{ result: Record<string, unknown> }>("/api/generation", {
        method: "POST",
        body: JSON.stringify({
          source_text: source,
          mode,
          output_length: "Medium",
          custom_prompt: mode === "Custom Prompt" ? customPrompt.trim() : "",
        }),
      });
      const generated = response.result;
      const generatedText = formatGenerationOutput(mode, generated);
      if (!generatedText) {
        throw new Error("The AI provider returned no usable text for this mode.");
      }
      setOutput(generatedText);
      setGenerationResult(generated);
      setHasOutput(true);
      setStatus("AI draft ready. Review and edit it before saving.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The AI request failed.");
    } finally {
      setBusy(false);
    }
  };

  const useExample = () => {
    setNote("I met Mina after class and we found a tiny bakery. The sunset made the walk home feel special. I need to send her the project notes tomorrow.");
    setVoiceText("");
    setOutput("");
    setHasOutput(false);
    setStatus("Example note loaded. Edit it, or try a voice note of your own.");
  };

  const saveDraft = async () => {
    if (!output.trim()) return;
    const structuredJournal = generationResult.structured_journal;
    const generatedTitle = typeof structuredJournal === "object" && structuredJournal !== null
      ? (structuredJournal as { title?: unknown }).title
      : undefined;
    const title = typeof generatedTitle === "string" && generatedTitle.trim()
      ? generatedTitle.trim()
      : mode === "Simple Journal" || mode === "Personal Persona"
        ? "A page from today"
        : `${mode} · ${readableDate(dateKey(new Date()))}`;
    setBusy(true);
    try {
      const generatedField = mode === "Simple Journal" || mode === "Personal Persona"
        ? "journal"
        : mode === "Reflection"
          ? "reflection"
          : mode === "Social Media"
            ? "social_caption"
            : "";
      const savedResult = {
        ...generationResult,
        ...(generatedField ? { [generatedField]: output } : {}),
        display_text: output,
      };
      await onSave(title, output, fullNote, mode, savedResult);
      setStatus("Your AI draft and original note were saved to your account.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not save this AI draft.");
    } finally {
      setBusy(false);
    }
  };

  const saveSuggestedTasks = async () => {
    const structuredDay = generationResult.structured_day;
    const pendingTasks = typeof structuredDay === "object" && structuredDay !== null
      ? (structuredDay as { pending_tasks?: unknown }).pending_tasks
      : undefined;
    const titles = Array.isArray(pendingTasks)
      ? pendingTasks.filter((task): task is string => typeof task === "string" && Boolean(task.trim()))
      : [];
    if (!titles.length) {
      setStatus("There are no pending task suggestions to save.");
      return;
    }
    setBusy(true);
    try {
      const { saved, failed } = await onCreateTasks(titles);
      setOutput(failed.length
        ? `Pending tasks · retry unsaved\n\n${failed.map((title) => `• ${title}`).join("\n")}`
        : "All suggested tasks have been saved to your task list.");
      setStatus(failed.length
        ? `${saved.length} task${saved.length === 1 ? "" : "s"} saved. ${failed.length} could not be saved; retry the remaining suggestions.`
        : `${saved.length} task${saved.length === 1 ? "" : "s"} saved to your account.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Could not save suggested tasks.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <div className="page-heading-row ai-studio-heading"><div><div className="eyebrow"><Wand2 size={14} /> YOUR LITTLE CREATIVE WORKSHOP</div><h1>AI <span>studio.</span></h1><p>Start with your voice or a few rough words. Shape them into a story that sounds like you.</p></div><div className="studio-badge"><BrainCircuit size={17} /><span>TRY THE WORKFLOW</span></div></div>
      <div className="studio-demo-banner"><Sparkles size={16} /><span><strong>Connected to the LifeLog API</strong> · AI generation requires an API key in the backend environment. Browser speech recognition is provided by your browser.</span></div>
      <div className="studio-step-row" aria-label="Note transformation steps"><span className="studio-step-active"><i>1</i> Capture a note</span><ArrowRight size={15} /><span><i>2</i> Choose a transformation</span><ArrowRight size={15} /><span><i>3</i> Review and save</span></div>
      <div className="studio-workspace">
        <section className="studio-panel studio-input-panel">
          <div className="studio-panel-heading"><span className="studio-section-icon"><AudioLines size={17} /></span><div><span className="section-kicker">STEP 01 · CAPTURE</span><h3>What happened today?</h3></div><button className="text-action" onClick={useExample}>Try an example</button></div>
          <div className={`voice-capture ${isListening ? "voice-capture-live" : ""}`}>
            <div className="voice-orb"><Mic size={19} /></div><div className="voice-capture-copy"><strong>{isListening ? "I’m listening…" : "Tell it in your own words"}</strong><span>Speech-to-text · {isListening ? "Live transcription" : "Browser powered"}</span></div>
            <button className={`voice-button ${isListening ? "voice-stop-button" : ""}`} onClick={isListening ? stopListening : startListening}>{isListening ? <><span className="voice-live-dot" /> Stop</> : <><Mic size={14} /> Record</>}</button>
            <div className="voice-wave" aria-hidden="true">{Array.from({ length: 25 }, (_, index) => <i key={index} />)}</div>
          </div>
          <div className={`voice-status ${isListening ? "voice-status-live" : ""}`} role="status"><span />{status}</div>
          <label className="studio-field-label" htmlFor="studio-note">Your note <span>edit the transcript or type instead</span></label>
          <textarea id="studio-note" className="studio-note-input" value={fullNote} onChange={(event) => { setNote(event.target.value); setVoiceText(""); setHasOutput(false); }} placeholder="Start with the little things. Where were you? Who was there? What would you like to remember?" rows={8} maxLength={2400} />
          <div className="studio-input-footer"><span><FileText size={13} /> Draft stays here until you save it to your account</span><span>{fullNote.length}/2400</span></div>
          <button className="studio-use-note" onClick={transformNote} disabled={busy}><Wand2 size={15} /> {busy ? "Working…" : "Shape my note"} <ArrowRight size={15} /></button>
        </section>
        <section className="studio-panel studio-output-panel">
          <div className="studio-panel-heading"><span className="studio-section-icon output-icon"><Wand2 size={17} /></span><div><span className="section-kicker">STEP 02 · TRANSFORM</span><h3>Give your words a shape</h3></div></div>
          <div className="transform-mode-grid">
            {([
              { name: "Simple Journal", icon: <BookHeart size={15} />, detail: "A grounded journal page" },
              { name: "Personal Persona", icon: <UserRound size={15} />, detail: "Your preferred voice" },
              { name: "Structured Day", icon: <Layers3 size={15} />, detail: "Events, moments, and tasks" },
              { name: "Reflection", icon: <Heart size={15} />, detail: "A gentle prompt" },
              { name: "Explain Through an Analogy", icon: <BrainCircuit size={15} />, detail: "A clear everyday comparison" },
              { name: "Vlog Creator", icon: <Clapperboard size={15} />, detail: "Scenes and voice-over" },
              { name: "Social Media", icon: <Sparkles size={15} />, detail: "Caption and story options" },
              { name: "Custom Prompt", icon: <Paintbrush2 size={15} />, detail: "Your own presentation rules" },
            ] as { name: TransformMode; icon: ReactNode; detail: string }[]).map((item) => <button key={item.name} className={`transform-mode ${mode === item.name ? "transform-mode-selected" : ""}`} onClick={() => { setMode(item.name); setHasOutput(false); }} aria-pressed={mode === item.name}><span>{item.icon}</span><strong>{item.name}</strong><small>{item.detail}</small>{mode === item.name && <Check size={13} className="mode-check" />}</button>)}
          </div>
          {mode === "Custom Prompt" && <label className="studio-field-label" htmlFor="studio-custom-prompt">Custom instructions<textarea id="studio-custom-prompt" className="studio-note-input" value={customPrompt} onChange={(event) => { setCustomPrompt(event.target.value); setHasOutput(false); }} placeholder="Describe the tone or format you want. Keep the facts grounded in your note." rows={3} maxLength={2000} /></label>}
          <div className="transformation-note"><Sparkles size={14} /><span>Pick an output style. You’ll be able to review it before saving anything.</span></div>
          <button className="studio-transform-button" onClick={transformNote} disabled={!fullNote.trim() || busy}><Wand2 size={16} /> {busy ? "Working…" : `Create ${mode.toLowerCase()} draft`} <ArrowRight size={15} /></button>
          <div className={`studio-result ${hasOutput ? "studio-result-ready" : ""}`}>
            <div className="studio-result-top"><span><span className="result-sparkle">✦</span> YOUR DRAFT</span><span>{hasOutput ? "READY TO REVIEW" : "WAITING FOR A NOTE"}</span></div>
            {hasOutput ? <><textarea aria-label={`${mode} draft`} className="studio-output-text" value={output} onChange={(event) => setOutput(event.target.value)} rows={8} />{mode === "Structured Day" ? <button className="create-button studio-save-button" onClick={() => void saveSuggestedTasks()} disabled={busy}><Save size={15} /> {busy ? "Saving…" : "Add pending tasks"}</button> : <button className="create-button studio-save-button" onClick={() => void saveDraft()} disabled={busy}><Save size={15} /> {busy ? "Saving…" : "Save to my memories"}</button>}</> : <div className="studio-placeholder"><div className="placeholder-paper"><span>✿</span><i /><i /><i /></div><strong>Your words, with a little structure.</strong><p>Choose an output style, then create a draft to review here.</p></div>}
          </div>
        </section>
      </div>
      <section className="studio-model-strip"><div><span className="section-kicker">THE GENERATIVE AI IDEA</span><h3>One moment. Many ways to keep it.</h3></div><div className="model-pipeline"><span><Mic size={15} /> Speech</span><ArrowRight size={14} /><span><BrainCircuit size={15} /> Understand</span><ArrowRight size={14} /><span><Wand2 size={15} /> Transform</span><ArrowRight size={14} /><span><BookHeart size={15} /> Remember</span></div></section>
    </>
  );
}

function VlogStudio({ memories, template, onTemplate, memoryId, onMemory, onGenerate }: {
  memories: Memory[];
  template: string;
  onTemplate: (template: string) => void;
  memoryId: string;
  onMemory: (id: string) => void;
  onGenerate: (memoryId: string, template: string) => Promise<string>;
}) {
  const [script, setScript] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const templates = [
    { name: "Soft storyboard", type: "6 FRAMES", description: "A gentle, scene-by-scene diary", className: "vlog-soft" },
    { name: "Scrapbook day", type: "COLLAGE", description: "Little clips, handwritten notes", className: "vlog-scrap" },
    { name: "Film diary", type: "MINI FILM", description: "A cinematic everyday recap", className: "vlog-film" },
  ];
  const selectedMemory = memories.find((memory) => memory.id === memoryId) ?? memories[0];
  const savedScript = selectedMemory?.result?.vlog_script;
  useEffect(() => {
    setScript(typeof savedScript === "string" ? savedScript : "");
    setError("");
  }, [selectedMemory?.id, savedScript]);

  const generate = async () => {
    if (!selectedMemory) return;
    setBusy(true);
    setError("");
    try {
      setScript(await onGenerate(selectedMemory.id, template));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not generate the storyboard.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="page-heading-row"><div><div className="eyebrow"><Clapperboard size={14} /> YOUR EVERYDAY, IN LITTLE FRAMES</div><h1>Vlog <span>studio.</span></h1><p>Turn a saved memory into a cozy storyboard for your next video.</p></div><div className="vlog-sticker">🎞️</div></div>
      <div className="vlog-disclaimer"><Sparkles size={15} /><span>Storyboard drafts are generated from your selected account memory using the configured AI provider.</span></div>
      <section className="vlog-template-section"><div className="section-heading"><div><span className="section-kicker">PICK YOUR PINBOARD VIBE</span><h3>What should your story feel like?</h3></div><span className="template-spark">✦</span></div><div className="vlog-template-grid">{templates.map((item, index) => <button key={item.name} className={`vlog-template ${item.className} ${template === item.name ? "vlog-template-active" : ""}`} onClick={() => { onTemplate(item.name); }} aria-pressed={template === item.name}><span className="template-art"><i className="template-art-sun" /><i className="template-art-paper" /><i className="template-art-photo" /><i className="template-art-flower">✿</i><i className="template-art-caption">{item.type}</i><i className="template-art-index">0{index + 1}</i></span><span className="template-copy"><strong>{item.name}</strong><small>{item.description}</small></span><span className="template-select">{template === item.name ? <Check size={14} /> : <Plus size={14} />}</span></button>)}</div></section>
      <section className="vlog-builder"><div className="vlog-builder-form"><span className="section-kicker">MAKE IT YOURS</span><h3>Choose a little moment</h3><label className="field-label" htmlFor="vlog-memory">Memory to turn into a vlog</label><select id="vlog-memory" className="profile-field" value={memoryId || selectedMemory?.id || ""} onChange={(event) => { onMemory(event.target.value); }} disabled={!memories.length}>{memories.length ? memories.map((memory) => <option value={memory.id} key={memory.id}>{memory.title} · {readableDate(memory.date)}</option>) : <option value="">Save a memory to get started</option>}</select><p className="vlog-helper">Your selected template: <strong>{template}</strong>. The generated script is saved with the selected memory.</p><button className="create-button" onClick={() => void generate()} disabled={!selectedMemory || busy}><Clapperboard size={15} /> {busy ? "Creating…" : "Arrange my storyboard"}</button>{error && <span className="auth-error" role="alert">{error}</span>}</div><div className={`vlog-preview ${templates.find((item) => item.name === template)?.className ?? ""}`}><div className="vlog-preview-toolbar"><span><span className="record-dot" /> ACCOUNT STORYBOARD</span><span>{template === "Film diary" ? "16:9" : "9:16"}</span></div>{script && selectedMemory ? <><div className="script-sheet"><span className="script-kicker">A LITTLE DAY, KEPT CLOSE</span><h4>{selectedMemory.title}</h4><div className="script-frames"><span>01</span><span>02</span><span>03</span></div><pre>{script}</pre></div><button className="script-download" onClick={() => { const url = URL.createObjectURL(new Blob([script], { type: "text/plain" })); const link = document.createElement("a"); link.href = url; link.download = "lifelog-vlog-storyboard.txt"; link.click(); URL.revokeObjectURL(url); }}><Save size={14} /> Download storyboard</button></> : <div className="vlog-preview-empty"><div className="preview-polaroid">✿<span>little frames<br />from your day</span></div><p>Choose a memory and a template<br />to generate a storyboard.</p></div>}</div></section>
    </>
  );
}

function MemoryComposer({ onClose, onSave }: { onClose: () => void; onSave: (entry: Omit<Memory, "id" | "color">) => Promise<void> }) {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [selectedMood, setSelectedMood] = useState<Mood>("Soft");
  const [template, setTemplate] = useState<JournalTemplate>("Soft pages");
  const [tag, setTag] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const save = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError("");
    try {
      await onSave({
        title: title.trim() || "A little moment",
        date: dateKey(new Date()),
        text: text.trim(),
        mood: selectedMood,
        tag: tag.trim() || "today",
        template,
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save your memory.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="composer-modal" role="dialog" aria-modal="true" aria-labelledby="composer-title">
        <div className="modal-top"><span className="modal-kicker"><Sparkles size={14} /> A PAGE THAT’S JUST YOURS</span><button className="icon-button" onClick={onClose} aria-label="Close"><X size={19} /></button></div>
        <div className="composer-title-row"><div><span className="eyebrow"><Sun size={13} /> {todayLabel}</span><h2 id="composer-title">What’s on your <span>heart?</span></h2></div><div className="composer-doodle">✿</div></div>
        <p className="composer-intro">There’s no right way to write this. A sentence, a list, a feeling — it all belongs.</p>
        <form onSubmit={save}>
          <label className="field-label" htmlFor="memory-title">Give this moment a name <span>optional</span></label>
          <input id="memory-title" className="composer-input" value={title} onChange={(event) => setTitle(event.target.value)} placeholder="e.g. The walk home in golden light" maxLength={70} />
          <label className="field-label" htmlFor="memory-story">Your little story</label>
          <textarea id="memory-story" className="composer-textarea" value={text} onChange={(event) => setText(event.target.value)} placeholder="What happened? What would you like to remember?..." rows={5} maxLength={1200} required autoFocus />
          <div className="textarea-footer"><span>Saved privately to your account when submitted.</span><span>{text.length}/1200</span></div>
          <span className="field-label">Choose a journal page</span>
          <div className="journal-template-options">{(["Soft pages", "Scrapbook", "Film diary"] as const).map((option) => <button type="button" key={option} className={`journal-template-choice ${template === option ? "journal-template-choice-active" : ""}`} onClick={() => setTemplate(option)} aria-pressed={template === option}><span className={`journal-template-mini journal-mini-${option.toLowerCase().replaceAll(" ", "-")}`}><i>✿</i><b /><em /></span><strong>{option}</strong><small>{option === "Soft pages" ? "A gentle journal page" : option === "Scrapbook" ? "Layered little keepsakes" : "A cinematic diary card"}</small></button>)}</div>
          <span className="field-label mood-label">How did it feel?</span>
          <div className="composer-moods">{moodOptions.map((option) => <button type="button" key={option.name} className={`composer-mood ${selectedMood === option.name ? "composer-mood-selected" : ""}`} onClick={() => setSelectedMood(option.name)} aria-pressed={selectedMood === option.name}><span>{option.face}</span>{option.name}</button>)}</div>
          {error && <span className="auth-error" role="alert">{error}</span>}
          <div className="composer-bottom"><label className="tag-input"><Tag size={14} /><input aria-label="Memory tag" placeholder="Add a little tag" value={tag} onChange={(event) => setTag(event.target.value)} maxLength={24} /></label><button type="submit" className="create-button" disabled={!text.trim() || busy}><Feather size={16} /> {busy ? "Saving…" : "Save this moment"}</button></div>
        </form>
        <div className="composer-privacy"><Heart size={13} /> Your words are yours. Always.</div>
      </section>
    </div>
  );
}

function MemoryDetail({ memory, onClose, onDelete }: { memory: Memory; onClose: () => void; onDelete: () => void }) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="composer-modal memory-detail-modal" role="dialog" aria-modal="true" aria-labelledby="memory-detail-title">
        <div className="modal-top"><span className="modal-kicker"><BookHeart size={14} /> KEPT CLOSE</span><button className="icon-button" onClick={onClose} aria-label="Close memory"><X size={19} /></button></div>
        <div className={`detail-art memory-${memory.color}`}><span>{readableDate(memory.date)}</span><i>✿</i></div>
        <div className="detail-meta"><span className="memory-mood">{moodOptions.find((option) => option.name === memory.mood)?.face} {memory.mood}</span><span className="memory-tag"><Tag size={11} /> {memory.tag}</span></div>
        <h2 id="memory-detail-title" className="detail-title">{memory.title}</h2>
        <p className="detail-story">{memory.text}</p>
        <div className="detail-footer"><span><Heart size={13} /> A little piece of your story.</span>{confirmDelete ? <div className="delete-confirm"><span>Remove this memory?</span><button onClick={onDelete}>Yes, remove</button><button onClick={() => setConfirmDelete(false)}>Keep it</button></div> : <button className="delete-memory-button" onClick={() => setConfirmDelete(true)}>Remove memory</button>}</div>
      </section>
    </div>
  );
}

export default App;
