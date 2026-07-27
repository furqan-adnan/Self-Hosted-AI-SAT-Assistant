import ASCIIText from '../../assets/components/ASCIIText';
import { SUGGESTIONS } from '../../config/constants';

export default function WelcomeScreen({ onSendSuggestion }: { onSendSuggestion: (text: string) => void }) {
  return (
    <div className="welcome">
      <div className="ascii-hero-wrapper">
        <ASCIIText
          text="SAT AI"
          enableWaves={true}
          asciiFontSize={8}
          textFontSize={150}
          textColor="#ffffff"
          planeBaseHeight={8}
        />
      </div>
      <h2>Ready when you are</h2>
      <p>Ask a math or reading question, or request a full practice problem.</p>
      <div className="chip-row">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => onSendSuggestion(s)}>
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}
