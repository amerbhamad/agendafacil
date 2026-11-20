"""
Testes automatizados da API (biblioteca padrão do Python).
Executar a partir da raiz do projeto:  python tests/test_api.py
Usa um banco temporário e não altera o banco real.
"""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from datetime import date, timedelta
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))
os.environ["AGENDAFACIL_DB"] = os.path.join(tempfile.mkdtemp(), "teste.db")
import server  # noqa: E402


def proximo_dia_util():
    d = date.today() + timedelta(days=1)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d.isoformat()


class TestAgendaFacil(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.iniciar_banco()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.url = f"http://127.0.0.1:{cls.httpd.server_address[1]}/api"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def chamar(self, metodo, caminho, corpo=None, token=None):
        req = urllib.request.Request(self.url + caminho, method=metodo,
                                     data=json.dumps(corpo).encode() if corpo else None,
                                     headers={"Content-Type": "application/json",
                                              **({"Authorization": "Bearer " + token} if token else {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def login(self, email):
        status, r = self.chamar("POST", "/login", {"email": email, "senha": "123456"})
        self.assertEqual(status, 200)
        return r["token"]

    def test_login_invalido(self):
        status, _ = self.chamar("POST", "/login", {"email": "mariana@agendafacil.com", "senha": "errada"})
        self.assertEqual(status, 401)

    def test_rotas_exigem_autenticacao(self):
        self.assertEqual(self.chamar("GET", "/profissionais")[0], 401)

    def test_cadastro_e_email_duplicado(self):
        dados = {"nome": "Novo Cliente", "email": "novo@teste.com", "senha": "abcdef", "perfil": "cliente"}
        self.assertEqual(self.chamar("POST", "/cadastro", dados)[0], 201)
        self.assertEqual(self.chamar("POST", "/cadastro", dados)[0], 409)

    def test_jornada_completa_sem_conflito(self):
        """Jornada da persona Mariana: agenda com Carlos; ninguém mais pega o mesmo horário."""
        mariana = self.login("mariana@agendafacil.com")
        carlos = self.login("carlos@agendafacil.com")
        profs = self.chamar("GET", "/profissionais", token=mariana)[1]
        carlos_id = next(p["id"] for p in profs if p["nome"] == "Carlos Mendes")
        servicos = self.chamar("GET", f"/profissionais/{carlos_id}/servicos", token=mariana)[1]
        corte = next(s for s in servicos if s["nome"] == "Corte de cabelo")
        dia = proximo_dia_util()

        livres = self.chamar("GET", f"/horarios?servico_id={corte['id']}&data={dia}", token=mariana)[1]
        self.assertIn("15:00", livres)

        status, ag = self.chamar("POST", "/agendamentos", {"servico_id": corte["id"], "data": dia, "hora": "15:00"}, mariana)
        self.assertEqual(status, 201)
        self.assertEqual(ag["status"], "confirmado")

        # horário não aparece mais e nova tentativa é rejeitada
        livres = self.chamar("GET", f"/horarios?servico_id={corte['id']}&data={dia}", token=mariana)[1]
        self.assertNotIn("15:00", livres)
        self.assertEqual(self.chamar("POST", "/agendamentos", {"servico_id": corte["id"], "data": dia, "hora": "15:00"}, mariana)[0], 409)

        # Carlos enxerga o compromisso na agenda
        agenda = self.chamar("GET", "/agendamentos", token=carlos)[1]
        self.assertTrue(any(a["id"] == ag["id"] and a["cliente"] == "Mariana Souza" for a in agenda))

        # cancelamento libera o horário novamente
        self.assertEqual(self.chamar("DELETE", f"/agendamentos/{ag['id']}", token=mariana)[0], 200)
        livres = self.chamar("GET", f"/horarios?servico_id={corte['id']}&data={dia}", token=mariana)[1]
        self.assertIn("15:00", livres)

    def test_conflito_por_duracao(self):
        """Serviço de 60 min às 10:00 bloqueia 10:00 e 10:30 para um serviço de 30 min."""
        mariana = self.login("mariana@agendafacil.com")
        carlos_id = next(p["id"] for p in self.chamar("GET", "/profissionais", token=mariana)[1] if p["nome"] == "Carlos Mendes")
        servs = {s["nome"]: s for s in self.chamar("GET", f"/profissionais/{carlos_id}/servicos", token=mariana)[1]}
        dia = proximo_dia_util()
        dia = (date.fromisoformat(dia) + timedelta(days=7)).isoformat()
        self.assertEqual(self.chamar("POST", "/agendamentos", {"servico_id": servs["Corte + Barba"]["id"], "data": dia, "hora": "10:00"}, mariana)[0], 201)
        livres = self.chamar("GET", f"/horarios?servico_id={servs['Barba']['id']}&data={dia}", token=mariana)[1]
        self.assertNotIn("10:00", livres)
        self.assertNotIn("10:30", livres)
        self.assertIn("11:00", livres)

    def test_data_passada_e_invalida(self):
        mariana = self.login("mariana@agendafacil.com")
        self.assertEqual(self.chamar("GET", "/horarios?servico_id=1&data=2020-01-01", token=mariana)[1], [])
        self.assertEqual(self.chamar("GET", "/horarios?servico_id=1&data=abc", token=mariana)[0], 400)

    def test_profissional_nao_agenda_e_cliente_nao_cadastra_servico(self):
        mariana = self.login("mariana@agendafacil.com")
        carlos = self.login("carlos@agendafacil.com")
        self.assertEqual(self.chamar("POST", "/agendamentos", {"servico_id": 1, "data": proximo_dia_util(), "hora": "09:00"}, carlos)[0], 403)
        self.assertEqual(self.chamar("POST", "/servicos", {"nome": "X", "preco": 10, "duracao_min": 30}, mariana)[0], 403)

    def test_profissional_cadastra_servico(self):
        carlos = self.login("carlos@agendafacil.com")
        status, s = self.chamar("POST", "/servicos", {"nome": "Sobrancelha", "preco": 15, "duracao_min": 15}, carlos)
        self.assertEqual(status, 201)
        self.assertEqual(self.chamar("POST", "/servicos", {"nome": "", "preco": -1, "duracao_min": 0}, carlos)[0], 400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
