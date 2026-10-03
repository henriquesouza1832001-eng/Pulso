-- Pico de cada evento: o nível/pulso atuais decaem com o tempo, mas o histórico de inteligência
-- (momentos de nível alto) precisa lembrar do máximo atingido e de quando.
ALTER TABLE events ADD COLUMN peak_alert_level INTEGER NOT NULL DEFAULT 1;
ALTER TABLE events ADD COLUMN peak_pulse INTEGER NOT NULL DEFAULT 0;
ALTER TABLE events ADD COLUMN peak_at TEXT;

-- Eventos já gravados: o melhor palpite disponível é o estado atual.
UPDATE events SET peak_alert_level = alert_level, peak_pulse = pulse, peak_at = updated_at;

CREATE INDEX idx_events_peak ON events (peak_alert_level, peak_at DESC);
