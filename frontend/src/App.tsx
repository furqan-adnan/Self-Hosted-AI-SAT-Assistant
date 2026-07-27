import Ferrofluid from './assets/components/Ferrofluid/Ferrofluid';
import SessionBar from './components/layout/SessionBar';
import WelcomeScreen from './components/welcome/WelcomeScreen';
import MessageRow from './components/chat/MessageRow';
import ThinkingIndicator from './components/chat/ThinkingIndicator';
import InputBar from './components/chat/InputBar';
import { useChat } from './hooks/useChat';
import './App.css';

function App() {
  const {
    messages,
    input,
    setInput,
    loading,
    statusText,
    isStreaming,
    connection,
    isBusy,
    sendMessage,
    scrollRef,
  } = useChat();

  return (
    <div className="sat-tutor-app">
      <div className="app-background">
        <Ferrofluid
          colors={["#3b82f6", "#1e40af", "#60a5fa"]}
          speed={0.4}
          scale={1.5}
          turbulence={0.8}
          fluidity={0.1}
          rimWidth={0.2}
          sharpness={3}
          glow={3}
          opacity={1}
          mouseInteraction={true}
        />
      </div>
      
      <SessionBar connection={connection} />

      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <WelcomeScreen onSendSuggestion={sendMessage} />
        )}

        {messages.map((msg, index) => (
          <MessageRow
            key={index}
            msg={msg}
            isStreaming={isStreaming}
            isLast={index === messages.length - 1}
          />
        ))}

        {loading && <ThinkingIndicator statusText={statusText} />}
      </div>

      <InputBar
        input={input}
        isBusy={isBusy}
        onInputChange={setInput}
        onSend={() => sendMessage()}
      />
    </div>
  );
}

export default App;