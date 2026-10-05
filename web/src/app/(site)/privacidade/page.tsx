import type { Metadata } from "next";

import { Contact, LEGAL, LegalPage, List, Section } from "@/components/Legal";

export const metadata: Metadata = {
  title: "Política de Privacidade · ImobiQ",
  description: "Quais dados o ImobiQ trata, para quê, com quem compartilha e como pedir a exclusão.",
};

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Política de Privacidade"
      intro={
        <>
          O ImobiQ é uma prova de conceito acadêmica de atendimento imobiliário com inteligência artificial,
          desenvolvida para o Hackathon da Pós Tech FIAP (IA para Devs). Esta política explica, de forma direta, quais
          dados pessoais o ImobiQ trata, para quê e quais são os seus direitos, conforme a Lei Geral de Proteção de Dados
          (Lei nº 13.709/2018).
        </>
      }
    >
      <Section title="1. Quem é o responsável">
        <p>
          O responsável pelo tratamento dos dados (controlador) é {LEGAL.owner}, autor do projeto. Para qualquer assunto
          sobre privacidade, escreva para <Contact />.
        </p>
      </Section>

      <Section title="2. Quais dados tratamos">
        <p>
          <strong className="font-medium text-ink">De quem conversa com a Laris</strong> (no chat, no widget de um site ou
          no Telegram):
        </p>
        <List>
          <li>as mensagens que você escreve e as respostas da assistente;</li>
          <li>
            os dados que você informar na conversa, como nome, telefone, empresa, cargo e o que procura em um imóvel
            (finalidade, região, orçamento, metragem, prazo);
          </li>
          <li>
            a página em que você estava ao abrir o chat, o imóvel que estava vendo e a origem da visita (endereço de
            origem e parâmetros de campanha);
          </li>
          <li>no Telegram, o identificador da conversa, o primeiro nome, o nome de usuário e o telefone, se você o compartilhar;</li>
          <li>os agendamentos de visita ou reunião feitos pela conversa.</li>
        </List>
        <p>
          O endereço IP é usado apenas na memória do servidor, por até uma hora, para limitar abusos (excesso de
          mensagens). Ele não é gravado no banco de dados.
        </p>
        <p>
          <strong className="font-medium text-ink">De quem entra na área restrita</strong> (equipe convidada):
        </p>
        <List>
          <li>e-mail, nome, papel de acesso e data do último acesso;</li>
          <li>a senha, guardada apenas na forma de um código irreversível (hash com sal), nunca em texto;</li>
          <li>
            se você entrar com a conta Google: nome, e-mail e foto do perfil, fornecidos pelo Google. O ImobiQ não
            recebe a sua senha do Google nem acessa contatos, e-mails, agenda ou arquivos.
          </li>
        </List>
        <p>Não pedimos nem tratamos de propósito dados sensíveis, e o serviço não se destina a menores de 18 anos.</p>
      </Section>

      <Section title="3. Para que usamos">
        <List>
          <li>responder às suas mensagens, entender o que você procura e sugerir imóveis;</li>
          <li>agendar a visita ou a reunião e avisar o corretor responsável, com um resumo do atendimento;</li>
          <li>retomar o contato quando a conversa fica sem resposta (follow-up), pelo mesmo canal;</li>
          <li>identificar quem acessa a área restrita e aplicar as permissões de cada papel;</li>
          <li>proteger o serviço contra abuso e medir custo, desempenho e qualidade das respostas.</li>
        </List>
        <p>
          As bases legais são o seu consentimento, ao iniciar a conversa e informar os dados, os procedimentos
          preliminares a um contrato, a seu pedido, e o legítimo interesse em manter o serviço seguro e funcionando.
        </p>
        <p>
          Os dados não são vendidos, não são usados para publicidade e não são usados por nós para treinar modelos de
          inteligência artificial.
        </p>
      </Section>

      <Section title="4. Dados recebidos do Google">
        <p>
          O login com Google é opcional. O nome, o e-mail e a foto recebidos são usados somente para identificar você
          na área restrita e mostrar o seu perfil na tela. Esses dados não são compartilhados com terceiros, não são
          usados para publicidade e não são usados para desenvolver ou treinar modelos de inteligência artificial. O uso
          de informações recebidas das APIs do Google segue a Política de Dados do Usuário dos Serviços de API do
          Google, incluindo os requisitos de uso limitado.
        </p>
      </Section>

      <Section title="5. Com quem compartilhamos">
        <p>Para funcionar, o ImobiQ usa prestadores de serviço que tratam dados em nosso nome:</p>
        <List>
          <li>
            <strong className="font-medium text-ink">Anthropic</strong> (modelos Claude): recebe o texto da conversa para
            gerar as respostas, extrair o perfil e escrever os resumos;
          </li>
          <li>
            <strong className="font-medium text-ink">Amazon Web Services</strong>: hospeda a aplicação e o banco de dados;
          </li>
          <li>
            <strong className="font-medium text-ink">Langfuse</strong>: registra o funcionamento das chamadas à IA para
            diagnóstico. Telefone, e-mail, CPF e CNPJ são mascarados antes do envio;
          </li>
          <li>
            <strong className="font-medium text-ink">Hostinger</strong>: envia os e-mails (resumo ao corretor, convite e
            redefinição de senha);
          </li>
          <li>
            <strong className="font-medium text-ink">Telegram</strong>: quando você escolhe conversar por lá;
          </li>
          <li>
            <strong className="font-medium text-ink">Google</strong>: quando você escolhe entrar com a conta Google.
          </li>
        </List>
        <p>
          Parte desses serviços fica fora do Brasil, principalmente nos Estados Unidos, então os dados podem ser
          transferidos para outros países. Também podemos fornecer dados quando a lei ou uma ordem judicial exigir.
        </p>
      </Section>

      <Section title="6. Cookies e armazenamento no navegador">
        <List>
          <li>
            um cookie de sessão, essencial, mantém você conectado à área restrita por até 12 horas. Ele não é lido por
            scripts da página;
          </li>
          <li>um cookie temporário, de até 10 minutos, protege o login com Google;</li>
          <li>o chat guarda no seu navegador o identificador da conversa, para você continuar de onde parou.</li>
        </List>
        <p>Não usamos cookies de publicidade nem ferramentas de rastreamento de terceiros.</p>
      </Section>

      <Section title="7. Por quanto tempo guardamos">
        <p>
          Por se tratar de um projeto acadêmico, as conversas e os cadastros são mantidos somente enquanto durar a
          demonstração e a avaliação do projeto, e podem ser apagados a qualquer momento, inclusive por rotinas que
          reiniciam os dados de demonstração. Você pode pedir a exclusão antes disso.
        </p>
      </Section>

      <Section title="8. Como protegemos">
        <List>
          <li>conexão criptografada (HTTPS) em todo o site;</li>
          <li>área restrita com login, papéis de acesso e sessão que expira;</li>
          <li>senhas guardadas apenas como hash, com limite de tentativas de login;</li>
          <li>limite de mensagens e proteções contra o uso indevido da assistente.</li>
        </List>
        <p>Nenhum sistema é totalmente imune a falhas. Se houver um incidente relevante com os seus dados, você será avisado.</p>
      </Section>

      <Section title="9. Seus direitos">
        <p>
          Você pode, a qualquer momento, pedir a confirmação de que tratamos os seus dados, o acesso a eles, a correção,
          a exclusão, a portabilidade, informações sobre o compartilhamento e a revogação do consentimento. Basta
          escrever para <Contact />. Respondemos em até 15 dias. Você também pode reclamar à Autoridade Nacional de
          Proteção de Dados (ANPD).
        </p>
      </Section>

      <Section title="10. Mudanças nesta política">
        <p>
          Esta política pode ser atualizada para refletir mudanças no projeto. A versão em vigor é sempre a publicada
          nesta página, com a data da última atualização no topo.
        </p>
      </Section>
    </LegalPage>
  );
}
