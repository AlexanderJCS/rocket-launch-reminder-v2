import logging
import re

from src.emailer.email_receiver import EmailReceiver
from src.emailer import emailer


class Subscriber:
    def __init__(self, receiver: EmailReceiver, config: dict, secret: dict):
        self._receiver = receiver
        self._secret = secret
        self._config = config

        self.last_email_date = self._receiver.get_last_email()["date"]

    def _add_subscription(self, email: str) -> None:
        """
        Adds a subscription to the _secret file.

        :param email: The email to add
        """

        self._secret["receiver"]["emails"].append(email)
        self._secret["receiver"]["emails"] = list(set(self._secret["receiver"]["emails"]))

    def _remove_subscription(self, email: str) -> None:
        """
        Removes a subscription from the secret file.

        :param email: The email to remove
        """

        try:
            self._secret["receiver"]["emails"].remove(email)

        except ValueError:
            pass

    @staticmethod
    def _get_email_contents(email) -> list[str]:
        """
        All relevant contents of an email that you may want to use for subscription checking.

        :return: A list of strings to search for "subscribe" or "unsubscribe" in
        """

        # A list of strings to search for "subscribe" or "unsubscribe" in
        email_contents: list[str | None] = [email["Subject"]]

        # Add any plaintext attachments to the list of strings to search
        if not email.is_multipart():
            return email_contents

        for part in email.walk():
            content_type = part.get_content_type()

            if content_type != "text/plain" and content_type != "text/html":
                continue

            email_contents.append(part.get_payload(decode=True).decode())

        return email_contents

    def _handle_subscription(self, email, subscribe: bool) -> None:
        """
        Handles a subscription.

        :param email: The email to subscribe or unsubscribe
        :param subscribe: Whether to subscribe or unsubscribe
        """

        if subscribe and email["From"]:
            logging.info(f"Adding {email['From']} to the subscription list")
            self._add_subscription(email["From"])

        else:
            logging.info(f"Removing {email['From']} from the subscription list")
            self._remove_subscription(email["From"])

        sub_or_unsub = "subscribe" if subscribe else "unsubscribe"

        emailer.send_email(
            body=self._config["subscription"][sub_or_unsub]["message"],
            subject=self._config["subscription"][sub_or_unsub]["subject"],
            to=email["From"],
            sender=self._secret["sender"]["username"],
            password=self._secret["sender"]["password"]
        )

    def _emailer_in_blacklist(self, email: str) -> bool:
        """
        Checks if the emailer is in the blacklist.

        :param email: The email to check
        :return: Whether the emailer is in the blacklist
        """

        return any(
            re.findall(blacklist_entry, email)

            for blacklist_entry in self._config["subscription"]["subscribe"]["blacklist"]
        )

    def check(self) -> bool:
        """
        Checks for new subscriptions and unsubscriptions.

        :return: If changes were made to the _secret file
        """

        email = self._receiver.get_last_email()

        if (email is None
                or email["date"] == self.last_email_date
                or self._emailer_in_blacklist(email["From"])):
            return False

        self.last_email_date = email["date"]

        # Search email contents for "subscribe" or "unsubscribe"
        email_contents = self._get_email_contents(email)

        # Subscribe and unsubscribe if the email contains the relevant strings
        for content in email_contents:
            if content is None:
                continue

            if "unsubscribe" in content.lower().strip() == "unsubscribe":
                self._handle_subscription(email, False)
                return True

            elif "subscribe" in content.lower().strip():
                self._handle_subscription(email, True)
                return True

        return False

    def get_secret(self) -> dict:
        """
        :return: The secret file
        """

        return self._secret
