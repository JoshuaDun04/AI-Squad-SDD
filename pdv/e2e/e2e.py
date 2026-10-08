"""E2E do painel: roda contra API e painel no ar. Variáveis: WEB_URL, API_URL, GATEWAY_TOKEN, SHOTS_DIR."""
import os, time, uuid, httpx, re
from playwright.sync_api import sync_playwright, expect

WEB=os.environ.get("WEB_URL","http://localhost:8080"); API=os.environ.get("API_URL","http://localhost:8000")
TOKEN=os.environ["GATEWAY_TOKEN"]; SH=os.environ.get("SHOTS_DIR","e2e-shots"); os.makedirs(SH, exist_ok=True)
email=f"dono{uuid.uuid4().hex[:6]}@sabor.com"

def webhook(rid, texto, tel="5592991234567"):
    r=httpx.post(f"{API}/canal/webhook", headers={"X-Gateway-Token":TOKEN}, json={
        "tipo":"mensagem","restaurante_id":rid,"mensagem_id":uuid.uuid4().hex,"telefone":tel,
        "nome_perfil":"Maria","texto":texto})
    assert r.status_code==200, r.text

with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={"width":1280,"height":820})
    pg.goto(WEB); pg.screenshot(path=f"{SH}/01-entrar.png")
    pg.get_by_role("button", name="Primeiro acesso? Cadastre seu restaurante").click()
    pg.get_by_label("Nome do restaurante").fill("Sabor do Rio")
    pg.get_by_label("E-mail").fill(email); pg.get_by_label("Senha").fill("Forte#2026")
    pg.get_by_role("button", name="Cadastrar e entrar").click()
    expect(pg.get_by_role("heading", name="Pedidos do dia")).to_be_visible()
    expect(pg.locator(".marca-nome")).to_have_text("Sabor do Rio")

    # Cardápio pela interface
    pg.get_by_role("link", name="Cardápio").click()
    for cat,itens in [("Peixes",[("Tambaqui assado","45,90","Com baião e farofa"),("Pirarucu de casaca","52,90","")]),("Bebidas",[("Suco de cupuaçu","8,90","500 ml")])]:
        pg.get_by_label("Nova categoria").fill(cat); pg.get_by_role("button", name="Criar categoria").click()
        art=pg.locator("article.categoria", has_text=cat)
        expect(art).to_be_visible()
        for nome,preco,desc in itens:
            art.get_by_label("Nome do novo item").fill(nome)
            art.get_by_label("Descrição do novo item").fill(desc)
            art.get_by_label("Preço do novo item em reais").fill(preco)
            art.get_by_role("button", name="Adicionar item").click()
            expect(art.locator(".item-nome", has_text=nome)).to_be_visible()
    pg.screenshot(path=f"{SH}/02-cardapio.png", full_page=True)

    # Horários: abre todos os dias 00:00-23:59
    pg.get_by_role("link", name="Horários").click()
    for d in ["Segunda","Terça","Quarta","Quinta","Sexta","Sábado","Domingo"]:
        pg.get_by_label(d, exact=True).check()
        pg.get_by_label(f"{d}: abre às").fill("00:00"); pg.get_by_label(f"{d}: fecha às").fill("23:59")
    pg.get_by_role("button", name="Salvar horários").click()
    expect(pg.get_by_text("Horários salvos.")).to_be_visible()
    pg.screenshot(path=f"{SH}/03-horarios.png", full_page=True)

    # Equipe: usuário da cozinha
    pg.get_by_role("link", name="Equipe").click()
    pg.get_by_label("E-mail").fill("cozinha@"+email.split("@")[1].replace("sabor","sabor"+uuid.uuid4().hex[:4]))
    coz_email=pg.get_by_label("E-mail").input_value()
    pg.get_by_label("Senha inicial").fill("Cozinha#2026"); pg.get_by_label("Cozinha", exact=False).first.check()
    pg.get_by_role("button", name="Dar acesso").click()
    expect(pg.get_by_role("cell", name=coz_email)).to_be_visible()

    # WhatsApp
    pg.get_by_role("link", name="WhatsApp").click()
    pg.screenshot(path=f"{SH}/04-whatsapp.png")
    rid=pg.evaluate("JSON.parse(localStorage.getItem('pdv.sessao')).restaurante_id")

    # Cozinha em outra aba, com o usuário da cozinha
    ctx2=b.new_context(viewport={"width":1440,"height":900}); kds=ctx2.new_page()
    kds.goto(WEB); kds.get_by_label("E-mail").fill(coz_email); kds.get_by_label("Senha").fill("Cozinha#2026")
    kds.get_by_role("button", name="Entrar", exact=True).click()
    expect(kds.get_by_role("heading", name="Fila da cozinha")).to_be_visible()
    expect(kds.get_by_role("link", name="Cardápio")).to_have_count(0)

    # Cliente faz dois pedidos pelo WhatsApp (webhook do gateway)
    for t in ["oi","1","1","2","1","2","1","1","3","1","1","3","sem cebola no tambaqui","1"]: webhook(rid,t)
    t0=time.time()
    expect(kds.locator(".ticket", has_text="#1")).to_be_visible(timeout=5000)
    atraso=time.time()-t0
    expect(kds.locator(".ticket", has_text="#1").locator(".ticket-obs")).to_have_text("sem cebola no tambaqui")
    for t in ["oi","1","2","1","3","2","Rua 10 de Julho, 500, Centro","2","100","1"]: webhook(rid,t,tel="5592988887777")
    expect(kds.locator(".ticket", has_text="#2")).to_be_visible(timeout=5000)
    kds.locator(".ticket", has_text="#1").get_by_role("button", name="Começar preparo").click()
    expect(kds.locator('.coluna[data-status="Em preparo"] .ticket', has_text="#1")).to_be_visible(timeout=5000)
    kds.screenshot(path=f"{SH}/05-cozinha.png", full_page=True)
    kds.locator(".ticket", has_text="#1").get_by_role("button", name="Marcar pronto").click()
    expect(kds.locator('.coluna[data-status="Pronto"] .ticket', has_text="#1")).to_be_visible(timeout=5000)
    expect(kds.locator('.coluna[data-status="Pronto"] .ticket', has_text="#1").get_by_role("button")).to_have_count(0)  # cozinha não finaliza

    # Atendimento: detalhe e cancelamento do #2
    pg.get_by_role("link", name="Pedidos do dia").click()
    pg.get_by_role("button", name="#2").click()
    expect(pg.get_by_text("Rua 10 de Julho, 500, Centro")).to_be_visible()
    expect(pg.get_by_text("Dinheiro, troco para R$ 100,00")).to_be_visible()
    pg.screenshot(path=f"{SH}/06-pedido-detalhe.png", full_page=True)
    pg.get_by_label("Motivo do cancelamento").fill("Cliente desistiu por telefone")
    pg.get_by_role("button", name="Cancelar pedido").click()
    expect(pg.locator(".detalhe .selo")).to_have_text("Cancelado")
    expect(kds.locator(".ticket", has_text="#2")).to_have_count(0, timeout=5000)

    # Celular
    cel=b.new_context(viewport={"width":390,"height":844}, is_mobile=True)
    c=cel.new_page(); c.goto(WEB); c.screenshot(path=f"{SH}/07-celular-entrar.png")
    c.get_by_label("E-mail").fill(coz_email); c.get_by_label("Senha").fill("Cozinha#2026"); c.get_by_role("button", name="Entrar", exact=True).click()
    expect(c.locator(".ticket", has_text="#1")).to_be_visible()
    c.screenshot(path=f"{SH}/08-celular-cozinha.png", full_page=True)
    sw=c.evaluate("document.documentElement.scrollWidth"); assert sw<=390, sw
    print(f"E2E OK · pedido na fila em {atraso:.2f}s · sem rolagem horizontal no celular ({sw}px)")
    b.close()
