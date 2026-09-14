const EMAIL = /[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g;
const CPF = /\b\d{3}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?\d{2}\b/g;
const CNPJ = /\b\d{2}[.\s-]?\d{3}[.\s-]?\d{3}[\/\s-]?\d{4}[-\s]?\d{2}\b/g;
const RG = /\b\d{1,2}[.\s-]?\d{3}[.\s-]?\d{3}[-\s]?[0-9Xx]\b/g;
const PHONE = /(?<!\d)(?:\+?55[\s.-]?)?(?:\(?\d{2}\)?[\s.-]?)?(?:9?\d{4})[\s.-]?\d{4}(?!\d)/g;
const CARD_CANDIDATE = /(?<!\d)(?:\d[\s-]?){13,19}(?!\d)/g;
const CEP = /\b\d{5}[-\s]?\d{3}\b/g;

export function passesLuhn(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.length < 13 || digits.length > 19 || /^(\d)\1+$/.test(digits)) return false;
  let sum = 0;
  let double = false;
  for (let index = digits.length - 1; index >= 0; index -= 1) {
    let digit = Number(digits[index]);
    if (double) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
    double = !double;
  }
  return sum % 10 === 0;
}

export function sanitizeTicket(value: string) {
  return value
    .replace(EMAIL, "[email removido]")
    .replace(CNPJ, "[CNPJ removido]")
    .replace(CPF, "[CPF removido]")
    .replace(CARD_CANDIDATE, (candidate) => passesLuhn(candidate) ? "[cartão removido]" : "[número longo removido]")
    .replace(PHONE, "[telefone removido]")
    .replace(RG, "[RG removido]")
    .replace(CEP, "[CEP removido]")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 2500);
}

function normalized(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

export type RiskFlag = "prompt_injection" | "financial" | "cancellation" | "security" | "data_loss" | "legal" | "privileged_access";

export function detectRiskFlags(value: string): RiskFlag[] {
  const text = normalized(value);
  const rules: Array<[RiskFlag, RegExp]> = [
    ["prompt_injection", /ignore (as |todas as )?instrucoes|instrucoes anteriores|system prompt|mensagem de sistema|developer message|confidence\s*[:=]|operationaltype|responda apenas|finja que/],
    ["financial", /cobranc|cartao|fatura|pagamento|estorno|reembols|pix|boleto|debito|credito/],
    ["cancellation", /cancel/],
    ["security", /fraude|invad|phishing|vazamento|seguranca|roubad|suspeit/],
    ["data_loss", /perda de dados|perdi (meus |os )?dados|arquivos? apagados?|data loss/],
    ["legal", /processo judicial|advogad|procon|acao judicial|medida legal/],
    ["privileged_access", /administrador|admin\b|privilegio|root\b|acesso elevado/],
  ];
  return rules.filter(([, pattern]) => pattern.test(text)).map(([flag]) => flag);
}

export function isLowRiskIntent(value: string) {
  const text = normalized(value);
  return /como (usar|configurar|alterar)|onde (encontro|fica)|qual (o |a )?(plano|recurso|funcao)|duvida (sobre|de) produto|horario de atendimento|manual|documentacao/.test(text);
}
