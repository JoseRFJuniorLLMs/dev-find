from __future__ import annotations

import mimetypes
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from .config import Settings


class Mailer:
    def __init__(self, settings: Settings):
        self.s=settings

    def validate(self) -> None:
        required={
            "SMTP_HOST":self.s.smtp_host,
            "SMTP_USER":self.s.smtp_user,
            "SMTP_PASSWORD":self.s.smtp_password,
            "FROM_EMAIL":self.s.from_email,
            "APPLICANT_NAME":self.s.applicant_name,
            "APPLICANT_EMAIL":self.s.applicant_email
        }
        missing=[k for k,v in required.items() if not v]
        if missing:
            raise RuntimeError("Configuração ausente: " + ", ".join(missing))
        if not self.s.cv_path.exists():
            raise RuntimeError(f"CV não encontrado: {self.s.cv_path}")
        if not self.s.email_template.exists():
            raise RuntimeError(f"Template não encontrado: {self.s.email_template}")

    def render(self, company: str) -> tuple[str,str]:
        subject=self.s.email_subject.format(role=self.s.applicant_role,name=self.s.applicant_name,company=company)
        body=self.s.email_template.read_text(encoding="utf-8").format(
            company=company,name=self.s.applicant_name,role=self.s.applicant_role,
            city=self.s.applicant_city,phone=self.s.applicant_phone,email=self.s.applicant_email,
            linkedin=self.s.linkedin_url,github=self.s.github_url
        )
        return subject,body

    def build(self,to_email: str,company: str) -> EmailMessage:
        subject,body=self.render(company)
        msg=EmailMessage()
        msg["Subject"]=subject
        msg["From"]=formataddr((self.s.from_name or self.s.applicant_name,self.s.from_email))
        msg["To"]=to_email
        msg["Message-ID"]=make_msgid(domain=self.s.from_email.split("@")[-1])
        msg.set_content(body)
        mime,_=mimetypes.guess_type(str(self.s.cv_path))
        maintype,subtype=(mime or "application/pdf").split("/",1)
        msg.add_attachment(self.s.cv_path.read_bytes(),maintype=maintype,subtype=subtype,filename=self.s.cv_path.name)
        return msg

    def send(self,to_email: str,company: str) -> tuple[str,str]:
        self.validate()
        msg=self.build(to_email,company)
        smtp=smtplib.SMTP_SSL(self.s.smtp_host,self.s.smtp_port,timeout=30) if self.s.smtp_ssl else smtplib.SMTP(self.s.smtp_host,self.s.smtp_port,timeout=30)
        try:
            smtp.ehlo()
            if self.s.smtp_starttls and not self.s.smtp_ssl:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(self.s.smtp_user,self.s.smtp_password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                pass
        return str(msg["Message-ID"]),str(msg["Subject"])
