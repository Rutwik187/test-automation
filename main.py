import os
import requests
import xml.etree.ElementTree as ET

class APIAutomation:
    def __init__(self):
        self.url = "https://api.accelya.io/ha/uat/oc"
        self.subscription_key = "51e310c2f2454d97a1ec4dc789d809b0"
        self.responses_folder = "api_responses"
        
        # Get the directory containing the script
        script_dir = os.path.dirname(os.path.abspath(__file__))

        
        # Load XML templates using relative paths
        with open(os.path.join(script_dir, 'AS.txt'), 'r') as file:
            self.airshopping_template = file.read()
        with open(os.path.join(script_dir, 'OP.txt'), 'r') as file:
            self.offerprice_template = file.read()
        with open(os.path.join(script_dir, 'OC.txt'), 'r') as file:
            self.ordercreate_template = file.read()

    def format_xml(self, template, pseudocity, agtpwd, agy, origin, destination, departure_date, 
                    ResponseID=None, OfferID=None, OfferItemID=None):
        return template.format(
            pseudocity=pseudocity,
            agtpwd=agtpwd,
            agy=agy,
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            ResponseID=ResponseID or '',
            OfferID=OfferID or '',
            OfferItemID=OfferItemID or ''
        )

    def send_soap_request(self, xml_request):
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'Ocp-Apim-Subscription-Key': "51e310c2f2454d97a1ec4dc789d809b0"
        }
        response = requests.post(self.url, data=xml_request, headers=headers)
        response.raise_for_status()
        return response

    def save_response(self, filename, content):
        if not os.path.exists(self.responses_folder):
            os.makedirs(self.responses_folder)
        filepath = os.path.join(self.responses_folder, filename)
        with open(filepath, 'w') as file:
            file.write(content)

    def parse_air_shopping_response(self, xml_data):
        root = ET.fromstring(xml_data)
        price_classes = []
        for price_class in root.findall('.//PriceClass'):
            price_class_id = price_class.get('PriceClassID')
            name = price_class.find('Name').text
            code = price_class.find('Code').text
            price_classes.append((price_class_id, name, code))
            print(f"PriceClass: {code} - {name}")
        return price_classes, root

    def process_offers(self, root, selected_price_class, airshopping_response):
        offers = []
        for offer in root.findall('.//Offer'):
            flight_refs = offer.findall('.//FlightsOverview/FlightRef')
            for flight_ref in flight_refs:
                if flight_ref.get('PriceClassRef') == selected_price_class:
                    offers.append(offer)
                    break
        return offers

def main():
    # Initialize API automation
    api = APIAutomation()
    
    # Set parameters
    pseudocity = "BJBE"
    agtpwd = "Narayan1234"
    agy = "12992280"
    origin = "LAS"
    destination = "HNL"
    departure_date = "2024-12-02"
    
    # Step 1: Send AirShopping request
    airshopping_request = api.format_xml(
        api.airshopping_template, 
        pseudocity, agtpwd, agy, 
        origin, destination, departure_date
    )
    
    airshopping_response = api.send_soap_request(airshopping_request)
    api.save_response("AirShoppingResponse.xml", airshopping_response.text)
    
    # Step 2: Parse response and get price classes
    price_classes, root = api.parse_air_shopping_response(airshopping_response.text)
    
    if not price_classes:
        print("No price classes found in the response.")
        return
    
    # Step 3: Get user selection
    selected_code = input("\nEnter the PriceClass Code you want to use: ")
    
    # Step 4: Find selected price class
    selected_price_class = None
    for price_class_id, name, code in price_classes:
        if code == selected_code:
            selected_price_class = price_class_id
            break
    
    if not selected_price_class:
        print(f"No PriceClass found for code: {selected_code}")
        return
    
    # Step 5: Process offers
    offers = api.process_offers(root, selected_price_class, airshopping_response)
    
    if not offers:
        print("No offers found for the selected price class.")
        return
    
    # Step 6: Process each offer
    for offer in offers:
        offer_id = offer.get('OfferID')
        offer_item = offer.find('.//OfferItem')
        if offer_item is not None:
            offer_item_id = offer_item.get('OfferItemID')
            
            # Get price information
            total_price = offer.find('.//TotalPrice/DetailCurrencyPrice/Total')
            if total_price is not None:
                price = total_price.text
                currency = total_price.get('Code')
                print(f"\n=== Offer Details ===")
                print(f"OfferID: {offer_id}")
                print(f"OfferItemID: {offer_item_id}")
                print(f"Total Price: {price} {currency}")
            
            # Process OfferPrice request
            offerprice_request = api.format_xml(
                api.offerprice_template,
                pseudocity, agtpwd, agy,
                origin, destination, departure_date,
                ResponseID=root.find('.//ResponseID').text,
                OfferID=offer_id,
                OfferItemID=offer_item_id
            )
            
            offerprice_response = api.send_soap_request(offerprice_request)
            api.save_response("OfferPriceResponse.xml", offerprice_response.text)
            
            # Process OrderCreate if needed
            ordercreate_request = api.format_xml(
                api.ordercreate_template,
                pseudocity, agtpwd, agy,
                origin, destination, departure_date,
                ResponseID=root.find('.//ResponseID').text,
                OfferID=offer_id,
                OfferItemID=offer_item_id
            )
            
            ordercreate_response = api.send_soap_request(ordercreate_request)
            api.save_response("OrderCreateResponse.xml", ordercreate_response.text)

if __name__ == '__main__':
    main()