import type { Metadata } from "next";
import Link from "next/link";

import { Contact, LEGAL, LegalPage, List, Section } from "@/components/Legal";

export const metadata: Metadata = {
  title: "Termos de Uso · ImobiQ",
  description: "Regras de uso do ImobiQ, uma prova de conceito acadêmica de atendimento imobiliário com IA.",
};

export default function TermsPage() {
  return (
    <LegalPage
      title="Termos de Uso"
      intro={
        <>
          Estes termos valem para o uso do ImobiQ em {LEGAL.site.replace("https://", "")}, do chat da assistente Laris,
          do widget embutido em sites e do bot no Telegram. Ao usar o serviço, você concorda com eles. Se não concordar,
          não use o serviço.
        </>
      }
    >
      <Section title="1. O que é o ImobiQ">
        <p>
          O ImobiQ é uma prova de conceito acadêmica, desenvolvida por {LEGAL.owner} com o apoio dos colegas {LEGAL.team}, para
          o Hackathon da Pós Tech FIAP (IA para Devs). Ele demonstra um agente de pré-atendimento imobiliário com inteligência artificial: conversa
          com o interessado, entende a necessidade, sugere imóveis, agenda visitas e prepara um resumo para o corretor.
        </p>
        <p>
          <strong className="font-medium text-ink">É uma demonstração, não uma imobiliária.</strong> A &ldquo;Imobiliária
          Exemplo&rdquo;, os imóveis, os edifícios, os endereços, os preços, os corretores e as agendas são fictícios.
          Nada do que aparece no ImobiQ é uma oferta real de venda ou locação, e os agendamentos feitos pela conversa
          são simulados: nenhuma visita acontece de fato.
        </p>
      </Section>

      <Section title="2. Respostas geradas por inteligência artificial">
        <p>
          A Laris é uma assistente virtual. As respostas são geradas por modelos de linguagem e podem conter erros,
          imprecisões ou informações desatualizadas. Elas não são aconselhamento jurídico, financeiro, de investimento ou
          de engenharia. Estimativas de rentabilidade são ilustrativas e não são garantia de retorno. Não tome decisões
          com base apenas no que a assistente disser.
        </p>
      </Section>

      <Section title="3. Uso permitido">
        <p>Você se compromete a usar o serviço de boa-fé. Não é permitido:</p>
        <List>
          <li>tentar burlar as proteções, extrair as instruções internas da assistente ou induzi-la a agir fora do atendimento imobiliário;</li>
          <li>enviar conteúdo ilegal, ofensivo, discriminatório ou que viole direitos de outras pessoas;</li>
          <li>informar dados pessoais de terceiros sem autorização;</li>
          <li>sobrecarregar o serviço com acessos automatizados, ou tentar obter acesso a áreas e dados aos quais você não tem permissão;</li>
          <li>usar o serviço para fins comerciais.</li>
        </List>
        <p>Há limites de mensagens por conversa e por dia. O acesso pode ser suspenso em caso de abuso.</p>
      </Section>

      <Section title="4. Área restrita e contas">
        <p>
          O dashboard, os leads, a observabilidade e as configurações são restritos a pessoas convidadas. O acesso é
          feito com e-mail e senha ou, como alternativa, com a conta Google do mesmo e-mail. Você é responsável por
          manter a sua senha em sigilo e por tudo o que for feito com a sua conta. O acesso é pessoal, pode ter
          permissões diferentes conforme o papel atribuído e pode ser alterado ou encerrado a qualquer momento pelos
          administradores.
        </p>
      </Section>

      <Section title="5. Privacidade">
        <p>
          O tratamento de dados pessoais é descrito na{" "}
          <Link href="/privacidade" className="font-medium text-brand underline-offset-2 hover:underline">
            Política de Privacidade
          </Link>
          , que faz parte destes termos. Como o conteúdo da conversa é processado por serviços de inteligência
          artificial de terceiros, evite informar dados que você não queira compartilhar.
        </p>
      </Section>

      <Section title="6. Propriedade intelectual">
        <p>
          O código-fonte do ImobiQ é de {LEGAL.owner} e é distribuído sob a licença PolyForm Noncommercial 1.0.0, que
          permite o uso não comercial. Os nomes ImobiQ e Laris, a identidade visual e os textos do projeto não podem ser
          usados de forma a sugerir vínculo ou endosso sem autorização. As marcas de terceiros citadas pertencem aos
          seus donos.
        </p>
      </Section>

      <Section title="7. Disponibilidade">
        <p>
          O serviço é oferecido gratuitamente e no estado em que se encontra, sem garantia de funcionamento
          ininterrupto. Por ser uma demonstração, ele pode ficar fora do ar, ser alterado ou encerrado a qualquer
          momento, e os dados podem ser apagados sem aviso.
        </p>
      </Section>

      <Section title="8. Limitação de responsabilidade">
        <p>
          Na extensão permitida pela lei, o responsável pelo projeto não responde por perdas ou danos decorrentes do uso
          do serviço, de decisões tomadas com base nas respostas da assistente, de indisponibilidade ou de perda de
          dados. Nada nestes termos afasta direitos que a legislação garante a você.
        </p>
      </Section>

      <Section title="9. Mudanças nestes termos">
        <p>
          Estes termos podem ser atualizados. A versão em vigor é sempre a publicada nesta página, com a data da última
          atualização no topo. Continuar usando o serviço depois de uma mudança significa concordar com a nova versão.
        </p>
      </Section>

      <Section title="10. Lei aplicável e contato">
        <p>
          Estes termos são regidos pelas leis da República Federativa do Brasil. Dúvidas, pedidos e reclamações podem ser
          enviados para <Contact />.
        </p>
      </Section>
    </LegalPage>
  );
}
